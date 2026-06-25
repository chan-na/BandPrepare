"""Unit tests for the count-in click track (bandprepare.click).

Pure tensor synthesis — no models, no audio I/O — so these run fast and headless.
"""

from __future__ import annotations

import math

import pytest
import torch

from bandprepare import click
from bandprepare.pipeline import _fmt_bpm, _minus_filename

SR = 44100


def _beat_samples(bpm: float, sr: int = SR) -> int:
    return int(round(sr * 60.0 / bpm))


def test_shape_and_length():
    # 120 BPM, 1 bar of 4/4 → 4 beats × 0.5s = 2.0s, stereo by default.
    track = click.click_track(120, samplerate=SR, bars=1, beats_per_bar=4)
    assert track.shape == (2, _beat_samples(120) * 4)
    assert track.dtype == torch.float32


def test_length_scales_with_bars_and_beats():
    track = click.click_track(100, samplerate=SR, bars=2, beats_per_bar=3)
    assert track.shape[-1] == _beat_samples(100) * 2 * 3


def test_channel_count_respected():
    mono = click.click_track(120, samplerate=SR, channels=1)
    assert mono.shape[0] == 1
    # All channels identical (the click is centered).
    stereo = click.click_track(120, samplerate=SR, channels=2)
    assert torch.equal(stereo[0], stereo[1])


def test_clicks_at_beat_onsets_silence_between():
    bpm = 120
    bs = _beat_samples(bpm)
    track = click.click_track(bpm, samplerate=SR, bars=1, beats_per_bar=4)[0]
    # Each beat onset has audible energy in the first few ms ...
    for i in range(4):
        onset = track[i * bs : i * bs + 100]
        assert onset.abs().max() > 0.1, f"no click at beat {i}"
    # ... and the tail of each beat (well past the 50 ms burst) is silent.
    quiet = track[bs - 1000 : bs]  # last ~23 ms before beat 2
    assert quiet.abs().max() < 1e-4


def test_downbeat_is_distinct_from_other_beats():
    bpm = 120
    bs = _beat_samples(bpm)
    track = click.click_track(bpm, samplerate=SR, bars=1, beats_per_bar=4)[0]
    # The downbeat (beat 0) is louder than the plain beats (1..3).
    downbeat_peak = track[0:100].abs().max()
    beat_peak = track[bs : bs + 100].abs().max()
    assert downbeat_peak > beat_peak


def test_no_clipping():
    track = click.click_track(120, samplerate=SR)
    assert track.abs().max() <= 1.0


@pytest.mark.parametrize("bad", [0, -5, -0.1])
def test_non_positive_bpm_rejected(bad):
    with pytest.raises(ValueError):
        click.click_track(bad, samplerate=SR)


@pytest.mark.parametrize("bars,beats", [(0, 4), (1, 0), (-1, 4)])
def test_non_positive_meter_rejected(bars, beats):
    with pytest.raises(ValueError):
        click.click_track(120, samplerate=SR, bars=bars, beats_per_bar=beats)


def test_prepend_count_in_prefixes_mix_and_preserves_it():
    mix = torch.randn(2, 50000)
    out = click.prepend_count_in(mix, 120, samplerate=SR, bars=1, beats_per_bar=4)
    click_len = _beat_samples(120) * 4
    assert out.shape == (2, click_len + mix.shape[-1])
    # The original mix is preserved verbatim after the click track.
    assert torch.equal(out[:, click_len:], mix)


def test_prepend_matches_dtype_and_device():
    mix = torch.zeros(2, 1000, dtype=torch.float32)
    out = click.prepend_count_in(mix, 90, samplerate=SR)
    assert out.dtype == mix.dtype and out.device == mix.device


def test_fmt_bpm():
    assert _fmt_bpm(120.0) == "120"
    assert _fmt_bpm(120.5) == "120.5"
    assert _fmt_bpm(96) == "96"


def test_minus_filename_count_in_suffix():
    assert _minus_filename(["bass"], "wav") == "minus-bass.wav"
    assert _minus_filename(["bass"], "wav", 120) == "minus-bass-count120.wav"
    assert _minus_filename(["vocals", "bass"], "flac", 96.5) == "minus-vocals-bass-count96.5.flac"
    # A falsy/None tempo means "no count-in" → no suffix.
    assert _minus_filename(["bass"], "wav", None) == "minus-bass.wav"
