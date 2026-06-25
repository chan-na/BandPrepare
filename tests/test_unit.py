"""Fast unit tests that do not require model weights.

Run with: pytest -q
The heavy end-to-end separation is exercised manually (see docs/REFERENCE.md
"동작 확인 / Verified run") because it downloads large model weights and is slow
on CPU.
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
    assert stem.kind == "stem" and stem.id == "htdemucs_ft"
    assert stem.output_stems == ("vocals", "drums", "bass", "other")
    assert drum.kind == "drum" and drum.id == "mdx23c"
    assert drum.output_stems == ("kick", "snare", "toms", "hihat", "ride", "crash")


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
    # BandPrepareOutput/<name> next to the input file.
    assert default_output_dir("/music/My Song.mp3") == Path("/music/BandPrepareOutput/My Song")
    assert default_output_dir("song.mp3") == Path("BandPrepareOutput") / "song"


def _opts(**kw):
    # drum_model pinned to larsnet: these tests assert its 5-piece DRUM_STEMS
    # layout regardless of the registry default (mdx23c). drum_split pinned on
    # (the Options default is off) so the split-layout tests keep exercising it.
    base = dict(
        input_path=Path("song.wav"),
        output_dir=Path("out"),
        stems=list(STEM_ORDER),
        drum_model="larsnet",
        drum_split=True,
    )
    base.update(kw)
    return Options(**base)


def test_planned_outputs_full_with_drum_split():
    files = planned_outputs(_opts())
    names = {p.as_posix() for p in files}
    # non-drum instruments
    assert "out/instruments/vocals.wav" in names
    assert "out/instruments/bass.wav" in names
    # drums split into pieces; the full drums stem is also kept by default
    assert "out/instruments/drums.wav" in names
    for piece in DRUM_STEMS:
        assert f"out/drums/{piece}.wav" in names


def test_planned_outputs_mdx23c_six_pieces():
    files = planned_outputs(_opts(drum_model="mdx23c"))
    names = {p.as_posix() for p in files}
    for piece in ("kick", "snare", "toms", "hihat", "ride", "crash"):
        assert f"out/drums/{piece}.wav" in names
    # the full drums stem is kept by default alongside the pieces
    assert "out/instruments/drums.wav" in names


def test_planned_outputs_no_keep_drums_stem():
    files = planned_outputs(_opts(keep_drums_stem=False))
    names = {p.as_posix() for p in files}
    assert "out/instruments/drums.wav" not in names


def test_cli_keep_drums_stem_default_on():
    from bandprepare.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["song.mp3"]).keep_drums_stem is True
    assert parser.parse_args(["song.mp3", "--no-keep-drums-stem"]).keep_drums_stem is False
    assert parser.parse_args(["song.mp3", "--keep-drums-stem"]).keep_drums_stem is True


def test_cli_drum_split_default_off():
    from bandprepare.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["song.mp3"]).drum_split is False
    assert parser.parse_args(["song.mp3", "--drum-split"]).drum_split is True
    assert parser.parse_args(["song.mp3", "--no-drum-split"]).drum_split is False


def test_options_drum_split_default_off():
    assert Options(input_path=Path("song.wav"), output_dir=Path("out"),
                   stems=list(STEM_ORDER)).drum_split is False


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
            def separate(self, wav, sr, progress=True, progress_cb=None):
                # Mimic a chunked backend reporting model-internal progress.
                if progress_cb is not None:
                    progress_cb(0.5)
                    progress_cb(1.0)
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
    # Stage-boundary events carry a human msg; model-internal ticks come with
    # msg == "" and reuse the running stage's key.
    keys = [stage for stage, _f, msg in events if stage != "save" and msg]
    assert keys == [
        "start", "stem_model", "load_audio", "separate_stems", "stems_done",
        "drum_model", "separate_drums", "drums_done", "done",
    ]
    fracs = [f for _s, f, _m in events if f is not None]
    assert fracs == sorted(fracs)            # monotonically non-decreasing
    assert events[-1][0] == "done" and events[-1][1] == 1.0


def test_progress_callback_model_ticks_mapped_into_stage_window(tmp_path, monkeypatch):
    _rc, events = _run_with_fakes(
        monkeypatch, tmp_path, drum_split=True, stems=["vocals", "drums", "bass"])
    stem_ticks = [f for s, f, msg in events if s == "separate_stems" and not msg]
    drum_ticks = [f for s, f, msg in events if s == "separate_drums" and not msg]
    # The fake backend reports 0.5 and 1.0; they land inside each stage's slice
    # of the overall bar (stems 0.10→0.55 with drum split, drums 0.68→0.98).
    assert stem_ticks and all(0.10 <= f <= 0.55 for f in stem_ticks)
    assert drum_ticks and all(0.68 <= f <= 0.98 for f in drum_ticks)


def test_progress_callback_no_drum_split(tmp_path, monkeypatch):
    rc, events = _run_with_fakes(
        monkeypatch, tmp_path, drum_split=False, stems=["vocals", "drums", "bass"])
    assert rc == 0
    keys = [stage for stage, _f, msg in events if stage != "save" and msg]
    assert keys == ["start", "stem_model", "load_audio", "separate_stems", "stems_done", "done"]
    # Without drum split the stems stage owns the bar up to 0.85.
    stem_ticks = [f for s, f, msg in events if s == "separate_stems" and not msg]
    assert stem_ticks and all(0.10 <= f <= 0.85 for f in stem_ticks)


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


def test_demix_reports_chunk_progress():
    torch = pytest.importorskip("torch")
    from bandprepare.separation.roformer import _demix

    cfg = {
        "training": {"instruments": ["kick", "snare"]},
        "audio": {"chunk_size": 32},
        "inference": {"num_overlap": 2, "batch_size": 1},
    }

    class _Model:
        def __call__(self, arr):  # (B, C, T) -> (B, instruments, C, T)
            return torch.zeros(arr.shape[0], 2, arr.shape[1], arr.shape[2])

    fracs: list[float] = []
    out = _demix(cfg, _Model(), torch.zeros(2, 200), "cpu",
                 progress=False, progress_cb=fracs.append)
    assert set(out) == {"kick", "snare"}
    assert fracs and fracs == sorted(fracs)  # one tick per chunk, increasing
    assert fracs[-1] == 1.0


def test_demucs_chunk_estimate():
    from bandprepare.separation.stems import _estimate_total_chunks

    class _M:
        samplerate = 44100
        segment = 8.0

    # 60 s track, shifts=1, overlap 0.25 → 6 s stride → ~11 chunks.
    total = _estimate_total_chunks([_M()], 60 * 44100, shifts=1, overlap=0.25)
    assert 10 <= total <= 12
    # A bag of 4 sub-models (htdemucs_ft) runs each over the whole track.
    assert _estimate_total_chunks([_M()] * 4, 60 * 44100, 1, 0.25) == 4 * total


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
    # Mix-minus checkboxes mirror the stems; the group toggle starts off, which
    # disables its children.
    assert tuple(win._minus_checks) == default_stems
    assert not win._minus_group.isChecked()
    assert not any(cb.isEnabled() for cb in win._minus_checks.values())
    win._minus_group.setChecked(True)
    assert all(cb.isEnabled() for cb in win._minus_checks.values())
    assert not any(cb.isChecked() for cb in win._minus_checks.values())
    win._minus_group.setChecked(False)
    # The default model has drums -> drum-split group enabled, but it starts
    # off, which disables its sub-options.
    assert win._drum_group.isEnabled()
    assert not win._drum_group.isChecked()
    assert not win._drum_combo.isEnabled()
    assert not win._keep_drums_check.isEnabled()

    # Switch to a 2-stem vocals/instrumental model (no drums).
    idx = win._stem_combo.findData("mel_band_roformer")
    assert idx >= 0
    win._stem_combo.setCurrentIndex(idx)
    assert tuple(win._stem_checks) == ("vocals", "other")
    assert tuple(win._minus_checks) == ("vocals", "other")
    # Drum controls disabled when the model emits no drums stem.
    assert not win._drum_group.isEnabled()
    assert not win._drum_combo.isEnabled()
    assert not win._keep_drums_check.isEnabled()

    # Switch back to a 6-stem model -> the group is re-enabled, but its
    # sub-options stay disabled until the user turns the split on.
    idx = win._stem_combo.findData("htdemucs_6s")
    assert idx >= 0
    win._stem_combo.setCurrentIndex(idx)
    assert "drums" in win._stem_checks
    assert win._drum_group.isEnabled()
    assert not win._drum_combo.isEnabled()
    win._drum_group.setChecked(True)
    assert win._drum_combo.isEnabled()
    assert win._keep_drums_check.isEnabled()


def test_mainwindow_drum_split_off_disables_children_and_autochecks_keep():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    # Drum split defaults off -> its sub-options start disabled.
    assert not win._drum_group.isChecked()
    assert not win._drum_combo.isEnabled()
    assert not win._keep_drums_check.isEnabled()
    win._keep_drums_check.setChecked(False)

    # Turning drum split on enables the sub-options and auto-checks keep-drums.
    win._drum_group.setChecked(True)
    assert win._keep_drums_check.isChecked()
    assert win._drum_combo.isEnabled()

    # Turning it back off disables the sub-options again.
    win._drum_group.setChecked(False)
    assert not win._drum_combo.isEnabled()
    assert not win._keep_drums_check.isEnabled()


def test_mainwindow_progress_ticks_move_bar_without_log():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    # Model-internal tick: empty msg moves the bar but writes nothing to the log.
    win._on_progress("separate_stems", 0.42, "")
    assert win._progress.value() == 42
    assert win._log.toPlainText() == ""
    # Stage boundary: non-empty msg is logged as before.
    win._on_progress("stems_done", 0.55, "악기 분리 완료 / instruments separated")
    assert "instruments separated" in win._log.toPlainText()
    assert win._progress.value() == 55


def test_mainwindow_minus_group_off_yields_no_minus():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    win._input_edit.setText("/music/song.mp3")
    # A stem checked while the group toggle is off must not produce a mix-minus.
    win._minus_checks["bass"].setChecked(True)
    opts = win._collect_options()
    assert opts is not None
    assert opts.minus == []


def test_gui_window_icon_ships_with_package():
    pytest.importorskip("PySide6")
    _qapp()
    from PySide6.QtGui import QIcon

    from bandprepare.gui import app as gui_app

    # gui/app.py resolves the icon next to its own module; the PNG is generated
    # from assets/icon.svg by packaging/make_icons.py and must stay committed.
    icon_png = Path(gui_app.__file__).with_name("icon.png")
    assert icon_png.exists()
    assert not QIcon(str(icon_png)).isNull()


def test_mainwindow_set_input_prefills_default_output():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    win._set_input("/music/My Song.mp3")
    assert win._output_edit.text() == str(Path("/music/BandPrepareOutput/My Song"))


def test_mainwindow_collect_options_reads_widgets():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    win._input_edit.setText("/music/My Song.mp3")
    win._output_edit.setText("/out/My Song")
    # Keep only vocals; remove bass via mix-minus (group toggle must be on).
    for name, cb in win._stem_checks.items():
        cb.setChecked(name == "vocals")
    win._minus_group.setChecked(True)
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
    # Defaults flow through: drum split starts off; keep-drums checkbox is on.
    assert opts.stem_model == "htdemucs_ft"
    assert opts.drum_model == "mdx23c"
    assert opts.drum_split is False
    assert opts.keep_drums_stem is True


def test_mainwindow_collect_options_requires_input():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    win._input_edit.setText("")
    assert win._collect_options() is None


# --- URL / YouTube input ---------------------------------------------------


def test_mainwindow_url_collect_sets_source_url_and_no_paths():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    win._url_edit.setText("https://youtu.be/abc")
    opts = win._collect_options()
    assert opts is not None
    assert opts.source_url == "https://youtu.be/abc"
    assert opts.input_path is None
    # Blank output → worker names it after the title (under the home folder).
    assert opts.output_dir is None


def test_mainwindow_url_with_explicit_output_kept():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    win._url_edit.setText("https://youtu.be/abc")
    win._output_edit.setText("/out/here")
    opts = win._collect_options()
    assert opts is not None
    assert opts.source_url == "https://youtu.be/abc"
    assert opts.output_dir == Path("/out/here")


def test_mainwindow_url_and_file_are_mutually_exclusive():
    pytest.importorskip("PySide6")
    _qapp()
    from bandprepare.gui.app import MainWindow

    win = MainWindow()
    # Choosing a file pre-fills input + output; then typing a URL clears both so
    # the URL is used unambiguously.
    win._set_input("/music/song.mp3")
    assert win._input_edit.text() == "/music/song.mp3"
    win._on_url_edited("https://youtu.be/x")
    assert win._input_edit.text() == ""
    assert win._output_edit.text() == ""
    # Conversely, picking a file clears a previously typed URL.
    win._url_edit.setText("https://youtu.be/x")
    win._set_input("/music/other.mp3")
    assert win._url_edit.text() == ""


def test_worker_scale_pipeline_fraction():
    pytest.importorskip("PySide6")
    from bandprepare.gui.worker import _DOWNLOAD_BAR_SHARE, _scale_pipeline_fraction

    # File input: pipeline owns the whole bar, unchanged.
    assert _scale_pipeline_fraction(0.0, fetched=False) == 0.0
    assert _scale_pipeline_fraction(1.0, fetched=False) == 1.0
    # URL input: the download owns the first slice; pipeline fills the rest.
    assert _scale_pipeline_fraction(0.0, fetched=True) == _DOWNLOAD_BAR_SHARE
    assert _scale_pipeline_fraction(1.0, fetched=True) == 1.0
    assert _scale_pipeline_fraction(None, fetched=True) is None


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


# --- frozen-bundle duplicate-process guard ---------------------------------
# Regression for v0.1.0: a frozen run spawned a do-nothing second process (an
# empty GUI window) because tqdm builds a multiprocessing RLock that starts the
# resource_tracker, which re-executes the bundle. configure_multiprocessing()
# gives tqdm a plain threading lock so no mp primitive — hence no spawn.


def test_configure_multiprocessing_noop_when_not_frozen(monkeypatch):
    from bandprepare import _frozen_mp

    monkeypatch.delattr(_frozen_mp.sys, "frozen", raising=False)
    _frozen_mp.configure_multiprocessing()  # must not raise


def test_configure_multiprocessing_sets_non_mp_tqdm_lock(monkeypatch):
    tqdm_mod = pytest.importorskip("tqdm")
    from bandprepare import _frozen_mp

    cls = tqdm_mod.tqdm
    had_lock = hasattr(cls, "_lock")
    saved = getattr(cls, "_lock", None)
    try:
        monkeypatch.setattr(_frozen_mp.sys, "frozen", True, raising=False)
        _frozen_mp.configure_multiprocessing()
        lock = cls._lock
        assert lock is not None
        # TqdmDefaultWriteLock (the mp one) exposes .mp_lock; a threading lock doesn't.
        assert not hasattr(lock, "mp_lock")
    finally:
        if had_lock:
            cls._lock = saved
        elif hasattr(cls, "_lock"):
            del cls._lock


# ---------------------------------------------------------------------------
# _frozen_streams — windowed Windows builds start with sys.stdout/stderr = None
# (pythonw semantics); tqdm inside demucs then crashes with "'NoneType' object
# has no attribute 'write'". configure_std_streams() points None streams at
# devnull and leaves real streams alone.


def test_configure_std_streams_replaces_none_streams(monkeypatch):
    import sys

    from bandprepare._frozen_streams import configure_std_streams

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    configure_std_streams()
    try:
        sys.stdout.write("ok")  # the exact call that failed on Windows
        sys.stderr.write("ok")
    finally:
        sys.stdout.close()
        sys.stderr.close()


def test_configure_std_streams_keeps_real_streams():
    import sys

    from bandprepare._frozen_streams import configure_std_streams

    out, err = sys.stdout, sys.stderr
    configure_std_streams()
    assert sys.stdout is out
    assert sys.stderr is err
