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
from bandprepare.errors import DependencyError
from bandprepare.pipeline import Options, planned_outputs
from bandprepare.separation.drums import DRUM_STEMS
from bandprepare.separation.stems import STEM_ORDER


def test_parse_stems_all():
    assert parse_stems("all") == list(STEM_ORDER)


def test_parse_stems_subset_is_canonical_order():
    assert parse_stems("bass,vocals,drums") == ["vocals", "drums", "bass"]


def test_parse_stems_dedup_and_case():
    assert parse_stems("DRUMS,drums") == ["drums"]


def test_parse_stems_unknown():
    with pytest.raises(ValueError):
        parse_stems("vocals,kazoo")


def test_parse_stems_empty():
    with pytest.raises(ValueError):
        parse_stems(" , ")


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
