"""Fast unit tests that do not require model weights.

Run with: pytest -q
The heavy end-to-end separation is exercised manually (see README) because it
downloads large model weights and is slow on CPU.
"""

from __future__ import annotations

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
