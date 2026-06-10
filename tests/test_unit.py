"""Fast unit tests that do not require model weights.

Run with: pytest -q
The heavy end-to-end separation is exercised manually (see README) because it
downloads large model weights and is slow on CPU.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bandprepare import device as device_mod
from bandprepare.cli import parse_stems, default_output_dir
from bandprepare.errors import DependencyError, ModelError
from bandprepare.pipeline import Options, planned_outputs
from bandprepare.separation import registry
from bandprepare.separation.drums import DRUM_STEMS
from bandprepare.separation.stems import STEM_ORDER


def test_parse_stems_all():
    assert parse_stems("all", STEM_ORDER) == list(STEM_ORDER)


def test_parse_stems_subset_is_canonical_order():
    assert parse_stems("bass,vocals,drums", STEM_ORDER) == ["vocals", "drums", "bass"]


def test_parse_stems_dedup_and_case():
    assert parse_stems("DRUMS,drums", STEM_ORDER) == ["drums"]


def test_parse_stems_unknown():
    with pytest.raises(ValueError):
        parse_stems("vocals,kazoo", STEM_ORDER)


def test_parse_stems_empty():
    with pytest.raises(ValueError):
        parse_stems(" , ", STEM_ORDER)


def test_parse_stems_rejects_stem_not_in_model():
    # guitar/piano are not produced by a 4-stem model.
    four = ("vocals", "drums", "bass", "other")
    with pytest.raises(ValueError):
        parse_stems("vocals,guitar", four)
    assert parse_stems("all", four) == list(four)


def test_registry_defaults_resolve():
    stem = registry.resolve_stem(registry.DEFAULT_STEM_MODEL)
    drum = registry.resolve_drum(registry.DEFAULT_DRUM_MODEL)
    assert stem.kind == "stem" and stem.output_stems == STEM_ORDER
    assert drum.kind == "drum" and drum.output_stems == DRUM_STEMS


def test_registry_unknown_model_raises():
    with pytest.raises(ModelError):
        registry.resolve_stem("does_not_exist")
    with pytest.raises(ModelError):
        registry.resolve_drum("does_not_exist")


def test_list_models_table_mentions_models():
    table = registry.format_table()
    assert registry.DEFAULT_STEM_MODEL in table
    assert registry.DEFAULT_DRUM_MODEL in table


def test_registry_has_added_models():
    # Phase 1/2 additions are registered with the expected output stems.
    assert set(registry.stem_model_ids()) >= {
        "htdemucs_6s", "htdemucs_ft", "bs_roformer", "mel_band_roformer"}
    assert set(registry.drum_model_ids()) >= {"larsnet", "drumsep"}
    assert registry.resolve_stem("htdemucs_ft").output_stems == ("vocals", "drums", "bass", "other")
    assert registry.resolve_stem("bs_roformer").output_stems == ("vocals", "drums", "bass", "other")
    # Mel-Band is a 2-stem vocals/instrumental model (no drums) → drum-split off.
    assert registry.resolve_stem("mel_band_roformer").output_stems == ("vocals", "other")
    assert set(registry.drum_model_ids()) >= {"larsnet", "drumsep", "mdx23c"}
    assert registry.resolve_drum("drumsep").output_stems == ("kick", "snare", "toms", "cymbals")


def test_registry_mdx23c_drum_model():
    info = registry.resolve_drum("mdx23c")
    assert info.kind == "drum"
    assert info.samplerate == 44100
    assert info.output_stems == ("kick", "snare", "toms", "hihat", "ride", "crash")
    # MDX23C is the only drum model that splits cymbals into separate ride/crash.
    assert "ride" in info.output_stems and "crash" in info.output_stems


def test_mdx23c_model_builds_from_bundled_config():
    # Validates the vendored TFC-TDF v3 code + bundled config still construct and
    # emit (B, stems, channels, samples) — the contract _demix relies on. Needs
    # torch but no downloaded weights, so it stays a "fast" test where torch exists.
    pytest.importorskip("torch")
    import torch

    from bandprepare.separation.mdx23c import _DotConfig, _load_config
    from bandprepare.vendor.mdx23c import TFC_TDF_net

    cfg = _load_config()
    assert cfg["training"]["instruments"] == ["kick", "snare", "toms", "hh", "ride", "crash"]
    model = TFC_TDF_net(_DotConfig(cfg)).eval()
    assert model.num_target_instruments == 6
    chunk = int(cfg["audio"]["chunk_size"])
    with torch.inference_mode():
        out = model(torch.zeros(1, cfg["audio"]["num_channels"], chunk))
    assert tuple(out.shape) == (1, 6, 2, chunk)


def test_parse_stems_4stem_model_rejects_guitar():
    four = registry.resolve_stem("bs_roformer").output_stems
    with pytest.raises(ValueError):
        parse_stems("vocals,guitar", four)


def test_default_output_dir():
    assert default_output_dir("/music/My Song.mp3") == Path("output") / "My Song"


def _opts(**kw):
    base = dict(
        input_path=Path("song.wav"),
        output_dir=Path("out"),
        stems=list(STEM_ORDER),
    )
    base.update(kw)
    return Options(**base)


def test_planned_outputs_full_with_drum_split():
    files = planned_outputs(_opts())
    names = {p.as_posix() for p in files}
    # non-drum instruments
    assert "out/instruments/vocals.wav" in names
    assert "out/instruments/bass.wav" in names
    # drums split into pieces; full drums stem NOT kept by default
    assert "out/instruments/drums.wav" not in names
    for piece in DRUM_STEMS:
        assert f"out/drums/{piece}.wav" in names


def test_planned_outputs_mdx23c_six_pieces():
    files = planned_outputs(_opts(drum_model="mdx23c"))
    names = {p.as_posix() for p in files}
    for piece in ("kick", "snare", "toms", "hihat", "ride", "crash"):
        assert f"out/drums/{piece}.wav" in names
    # drums stem is consumed by stage 2, not kept by default
    assert "out/instruments/drums.wav" not in names


def test_planned_outputs_keep_drums_stem():
    files = planned_outputs(_opts(keep_drums_stem=True))
    names = {p.as_posix() for p in files}
    assert "out/instruments/drums.wav" in names


def test_planned_outputs_no_drum_split():
    files = planned_outputs(_opts(drum_split=False))
    names = {p.as_posix() for p in files}
    assert "out/instruments/drums.wav" in names
    assert not any("/drums/" in n for n in names)


def test_planned_outputs_subset_no_drums():
    files = planned_outputs(_opts(stems=["vocals", "bass"]))
    names = {p.as_posix() for p in files}
    assert names == {"out/instruments/vocals.wav", "out/instruments/bass.wav"}


def test_planned_outputs_includes_minus():
    files = planned_outputs(_opts(minus=["bass"]))
    names = {p.as_posix() for p in files}
    assert "out/mixes/minus-bass.wav" in names


def test_planned_outputs_minus_multiple():
    files = planned_outputs(_opts(minus=["vocals", "bass"]))
    names = {p.as_posix() for p in files}
    assert "out/mixes/minus-vocals-bass.wav" in names


def test_compute_minus_subtracts_and_aligns_length():
    import torch

    from bandprepare.pipeline import compute_minus

    mix = torch.ones(2, 100)
    sources = {
        "vocals": torch.full((2, 100), 0.5),
        "bass": torch.full((2, 98), 0.25),  # shorter — exercises length alignment
    }
    out = compute_minus(mix, sources, ["vocals", "bass"])
    assert out.shape == (2, 98)  # trimmed to the shortest input
    assert torch.allclose(out, torch.full((2, 98), 0.25))


def test_compute_minus_does_not_mutate_mix():
    import torch

    from bandprepare.pipeline import compute_minus

    mix = torch.ones(2, 50)
    compute_minus(mix, {"bass": torch.ones(2, 50)}, ["bass"])
    assert torch.allclose(mix, torch.ones(2, 50))  # mix untouched


def test_cli_minus_unknown_stem_exits():
    from bandprepare.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["song.mp3", "--minus", "kazoo"])
    assert exc.value.code == 2


def _patch_device(monkeypatch, *, cuda, mps, apple_silicon):
    monkeypatch.setattr(device_mod, "_cuda_ok", lambda: cuda)
    monkeypatch.setattr(device_mod, "_mps_ok", lambda: mps)
    monkeypatch.setattr(device_mod, "_is_apple_silicon", lambda: apple_silicon)


def test_auto_prefers_cuda(monkeypatch):
    _patch_device(monkeypatch, cuda=True, mps=True, apple_silicon=True)
    assert device_mod.resolve_device("auto") == "cuda"


def test_auto_mps_only_on_apple_silicon(monkeypatch):
    _patch_device(monkeypatch, cuda=False, mps=True, apple_silicon=True)
    assert device_mod.resolve_device("auto") == "mps"


def test_auto_skips_mps_on_intel_mac(monkeypatch):
    # MPS "available" but Intel Mac -> auto must fall back to CPU, not MPS.
    _patch_device(monkeypatch, cuda=False, mps=True, apple_silicon=False)
    assert device_mod.resolve_device("auto") == "cpu"


def test_explicit_mps_forces_even_on_intel(monkeypatch):
    _patch_device(monkeypatch, cuda=False, mps=True, apple_silicon=False)
    assert device_mod.resolve_device("mps") == "mps"


def test_explicit_cuda_unavailable_errors(monkeypatch):
    _patch_device(monkeypatch, cuda=False, mps=False, apple_silicon=False)
    with pytest.raises(DependencyError):
        device_mod.resolve_device("cuda")


def test_unknown_device_errors():
    with pytest.raises(DependencyError):
        device_mod.resolve_device("tpu")


def test_make_sample_shape(tmp_path):
    import soundfile as sf

    from tests.make_sample import make_sample

    out = make_sample(tmp_path / "s.wav", seconds=1.0)
    data, sr = sf.read(str(out))
    assert sr == 44100
    assert data.shape[0] == 44100
    assert data.shape[1] == 2


# --- Phase 1: bundled ffmpeg resolution -----------------------------------

def test_resolve_ffmpeg_prefers_system(monkeypatch):
    from bandprepare import audio

    monkeypatch.setattr(audio.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(audio, "_bundled_ffmpeg_exe", lambda: "/bundled/ffmpeg")
    assert audio.resolve_ffmpeg() == "/usr/bin/ffmpeg"
    assert audio.ffmpeg_available() is True


def test_resolve_ffmpeg_falls_back_to_bundled(monkeypatch):
    from bandprepare import audio

    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    monkeypatch.setattr(audio, "_bundled_ffmpeg_exe", lambda: "/bundled/ffmpeg")
    assert audio.resolve_ffmpeg() == "/bundled/ffmpeg"
    assert audio.ffmpeg_available() is True
    audio.ensure_ffmpeg()  # must not raise when only the bundle exists


def test_ensure_ffmpeg_raises_when_none(monkeypatch):
    from bandprepare import audio
    from bandprepare.errors import DependencyError

    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    monkeypatch.setattr(audio, "_bundled_ffmpeg_exe", lambda: None)
    assert audio.ffmpeg_available() is False
    with pytest.raises(DependencyError):
        audio.ensure_ffmpeg()


def test_decode_with_ffmpeg_reshapes_interleaved_f32le(monkeypatch):
    import subprocess

    import numpy as np

    from bandprepare import audio

    # Two stereo frames: L0,R0, L1,R1 (interleaved).
    pcm = np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float32).tobytes()
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=pcm, stderr=b""),
    )
    wav = audio._decode_with_ffmpeg(Path("x.mp3"), channels=2, samplerate=44100, exe="ffmpeg")
    assert tuple(wav.shape) == (2, 2)
    assert wav[0].tolist() == [0.0, 2.0]  # channel 0 = L
    assert wav[1].tolist() == [1.0, 3.0]  # channel 1 = R


def test_prepare_ffmpeg_path_links_bundled(tmp_path, monkeypatch):
    from bandprepare import audio

    fake = tmp_path / "ffmpeg-macos-x86_64-v9"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setattr(audio, "_bundled_ffmpeg_exe", lambda: str(fake))
    monkeypatch.setattr(audio, "_ffmpeg_path_prepared", False)
    monkeypatch.setenv("PATH", str(tmp_path / "nothing-here"))  # no system ffmpeg
    monkeypatch.setenv("BANDPREPARE_CACHE", str(tmp_path / "cache"))

    out = audio.prepare_ffmpeg_path()
    assert out is not None
    # On Windows the link is ffmpeg.exe and shutil.which() reports ffmpeg.EXE
    # (PATHEXT casing); compare the extension-less, case-folded stem.
    assert Path(out).stem.lower() == "ffmpeg"
    assert audio.shutil.which("ffmpeg") == out  # now resolvable by bare name


def test_load_track_decodes_mp3_via_bundled_ffmpeg(tmp_path, monkeypatch):
    # End-to-end Phase 1 completion check: decode an mp3 with NO system
    # ffmpeg/ffprobe on PATH — only the bundled (ffprobe-less) path can work.
    pytest.importorskip("imageio_ffmpeg")
    import subprocess

    import numpy as np
    import soundfile as sf

    from bandprepare import audio

    exe = audio._bundled_ffmpeg_exe()
    if not exe:
        pytest.skip("bundled ffmpeg not available")

    sr = 44100
    n = int(sr * 0.2)
    tone = (0.1 * np.sin(2 * np.pi * 220 * np.arange(n) / sr)).astype(np.float32)
    data = np.stack([tone, tone], axis=1)
    wav_path = tmp_path / "a.wav"
    sf.write(str(wav_path), data, sr)
    mp3_path = tmp_path / "a.mp3"
    subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(wav_path), str(mp3_path)], check=True)

    monkeypatch.setenv("PATH", str(tmp_path / "nothing-here"))  # hide system ffmpeg/ffprobe
    wav = audio.load_track(mp3_path, channels=2, samplerate=sr)
    assert wav.shape[0] == 2
    assert wav.shape[1] > 0


# --- Phase 2: pipeline progress callback ----------------------------------

def _fake_info(kind, names):
    from bandprepare.separation.base import ModelInfo

    def load(info, device, **kw):
        import torch

        class _Sep:
            def separate(self, wav, sr, progress=True):
                return {n: torch.zeros(2, 100) for n in names}

        return _Sep()

    return ModelInfo(id=f"fake_{kind}", kind=kind, display=f"Fake {kind}",
                     output_stems=tuple(names), samplerate=44100, load=load)


def _run_with_fakes(monkeypatch, tmp_path, *, drum_split, stems, minus=None, callback="record"):
    import torch

    from bandprepare import pipeline

    stem_info = _fake_info("stem", ["vocals", "drums", "bass"])
    drum_info = _fake_info("drum", ["kick", "snare"])
    monkeypatch.setattr(pipeline.registry, "resolve_stem", lambda _id: stem_info)
    monkeypatch.setattr(pipeline.registry, "resolve_drum", lambda _id: drum_info)
    monkeypatch.setattr(pipeline, "resolve_device", lambda _c: "cpu")
    monkeypatch.setattr(pipeline.audio, "validate_input", lambda p: p)
    monkeypatch.setattr(pipeline.audio, "load_track", lambda p, ch, sr: torch.zeros(2, 100))
    monkeypatch.setattr(pipeline.audio, "save_waveform", lambda wav, path, sr, fmt: path)

    events: list[tuple] = []
    cb = (lambda stage, frac, msg: events.append((stage, frac, msg))) if callback == "record" else None
    opts = pipeline.Options(
        input_path=tmp_path / "song.wav",
        output_dir=tmp_path / "out",
        stems=stems,
        drum_split=drum_split,
        minus=minus or [],
        progress_callback=cb,
    )
    return pipeline.run(opts), events


def test_progress_callback_order_with_drum_split(tmp_path, monkeypatch):
    rc, events = _run_with_fakes(
        monkeypatch, tmp_path, drum_split=True, stems=["vocals", "drums", "bass"])
    assert rc == 0
    keys = [stage for stage, _f, _m in events if stage != "save"]
    assert keys == [
        "start", "stem_model", "load_audio", "separate_stems", "stems_done",
        "drum_model", "separate_drums", "drums_done", "done",
    ]
    fracs = [f for _s, f, _m in events if f is not None]
    assert fracs == sorted(fracs)            # monotonically non-decreasing
    assert events[-1][0] == "done" and events[-1][1] == 1.0


def test_progress_callback_no_drum_split(tmp_path, monkeypatch):
    rc, events = _run_with_fakes(
        monkeypatch, tmp_path, drum_split=False, stems=["vocals", "drums", "bass"])
    assert rc == 0
    keys = [stage for stage, _f, _m in events if stage != "save"]
    assert keys == ["start", "stem_model", "load_audio", "separate_stems", "stems_done", "done"]


def test_progress_callback_reports_minus(tmp_path, monkeypatch):
    _rc, events = _run_with_fakes(
        monkeypatch, tmp_path, drum_split=False, stems=["vocals", "bass"], minus=["bass"])
    assert "minus" in [stage for stage, _f, _m in events]


def test_run_without_callback_no_regression(tmp_path, monkeypatch):
    # No callback => emit() is a no-op and the run completes normally.
    rc, events = _run_with_fakes(
        monkeypatch, tmp_path, drum_split=True, stems=["vocals", "drums", "bass"], callback=None)
    assert rc == 0
    assert events == []


# --- Phase 3: PySide6 GUI --------------------------------------------------
# These skip cleanly when PySide6 is absent and always run offscreen so they
# need no display. pipeline.run is never called for real (no model downloads).

def _qapp():
    """A single shared offscreen QApplication for all GUI tests."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_build_options_maps_state():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import build_options

    opts = build_options(
        input_path=Path("/music/song.mp3"),
        output_dir=Path("/out/song"),
        stem_model="htdemucs_6s",
        drum_model="mdx23c",
        stems=["vocals", "drums"],
        minus=["bass"],
        fmt="flac",
        device_choice="cpu",
        drum_split=False,
        keep_drums_stem=True,
        overwrite=True,
        verbose=True,
    )
    assert opts.input_path == Path("/music/song.mp3")
    assert opts.output_dir == Path("/out/song")
    assert opts.stem_model == "htdemucs_6s"
    assert opts.drum_model == "mdx23c"
    assert opts.stems == ["vocals", "drums"]
    assert opts.minus == ["bass"]
    assert opts.fmt == "flac"
    assert opts.device_choice == "cpu"
    assert opts.drum_split is False
    assert opts.keep_drums_stem is True
    assert opts.overwrite is True
    assert opts.verbose is True


def test_mainwindow_stem_checkboxes_and_drum_controls():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()

    # Default model -> its full stem set, all checked.
    default_stems = registry.resolve_stem(registry.DEFAULT_STEM_MODEL).output_stems
    assert tuple(win._stem_checks) == default_stems
    assert all(cb.isChecked() for cb in win._stem_checks.values())
    # Mix-minus checkboxes mirror the stems but start unchecked.
    assert tuple(win._minus_checks) == default_stems
    assert not any(cb.isChecked() for cb in win._minus_checks.values())
    # A 6-stem model has drums -> drum controls enabled.
    assert win._drum_combo.isEnabled()
    assert win._drum_split_check.isEnabled()
    assert win._keep_drums_check.isEnabled()

    # Switch to a 2-stem vocals/instrumental model (no drums).
    idx = win._stem_combo.findData("mel_band_roformer")
    assert idx >= 0
    win._stem_combo.setCurrentIndex(idx)
    assert tuple(win._stem_checks) == ("vocals", "other")
    assert tuple(win._minus_checks) == ("vocals", "other")
    # Drum controls disabled when the model emits no drums stem.
    assert not win._drum_combo.isEnabled()
    assert not win._drum_split_check.isEnabled()
    assert not win._keep_drums_check.isEnabled()

    # Switch back to a 6-stem model -> drum controls re-enabled.
    idx = win._stem_combo.findData("htdemucs_6s")
    assert idx >= 0
    win._stem_combo.setCurrentIndex(idx)
    assert "drums" in win._stem_checks
    assert win._drum_combo.isEnabled()
    assert win._drum_split_check.isEnabled()
    assert win._keep_drums_check.isEnabled()


def test_mainwindow_collect_options_reads_widgets():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    win._input_edit.setText("/music/My Song.mp3")
    win._output_edit.setText("/out/My Song")
    # Keep only vocals; remove bass via mix-minus.
    for name, cb in win._stem_checks.items():
        cb.setChecked(name == "vocals")
    win._minus_checks["bass"].setChecked(True)
    win._fmt_combo.setCurrentText("mp3")
    win._device_combo.setCurrentText("cpu")

    opts = win._collect_options()
    assert opts is not None
    assert opts.input_path == Path("/music/My Song.mp3")
    assert opts.output_dir == Path("/out/My Song")
    assert opts.stems == ["vocals"]
    assert opts.minus == ["bass"]
    assert opts.fmt == "mp3"
    assert opts.device_choice == "cpu"


def test_mainwindow_collect_options_requires_input():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    win._input_edit.setText("")
    assert win._collect_options() is None


# --- frozen-bundle SSL CA wiring -------------------------------------------
# Regression for v0.1.0: a downloaded macOS bundle failed every weight download
# with CERTIFICATE_VERIFY_FAILED because the frozen OpenSSL had no usable CA
# path. configure_ssl_cert_file() points SSL_CERT_FILE at the bundled certifi.


def test_configure_ssl_cert_file_noop_when_not_frozen(monkeypatch):
    from bandprepare import _ssl_certs

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delattr(_ssl_certs.sys, "frozen", raising=False)
    assert _ssl_certs.configure_ssl_cert_file() is None
    assert "SSL_CERT_FILE" not in os.environ


def test_configure_ssl_cert_file_sets_certifi_when_frozen(monkeypatch):
    certifi = pytest.importorskip("certifi")
    from bandprepare import _ssl_certs

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    monkeypatch.setattr(_ssl_certs.sys, "frozen", True, raising=False)
    result = _ssl_certs.configure_ssl_cert_file()
    assert result == certifi.where()
    assert os.environ["SSL_CERT_FILE"] == certifi.where()
    assert os.environ["SSL_CERT_DIR"] == os.path.dirname(certifi.where())


def test_configure_ssl_cert_file_respects_user_override(monkeypatch):
    from bandprepare import _ssl_certs

    monkeypatch.setattr(_ssl_certs.sys, "frozen", True, raising=False)
    monkeypatch.setenv("SSL_CERT_FILE", "/custom/ca.pem")
    assert _ssl_certs.configure_ssl_cert_file() == "/custom/ca.pem"
    assert os.environ["SSL_CERT_FILE"] == "/custom/ca.pem"
