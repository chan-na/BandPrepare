"""Count-in click track synthesis for play-along (mix-minus) outputs.

Band-practice need: a mix-minus that starts the instant you hit play is hard to
come in on. Prepending a few metronome clicks at the song's tempo gives the band
a count-in ("1 2 3 4") so everyone enters together on the downbeat.

Pure torch — no new dependencies, and crucially none of the librosa/numba JIT
stack that the portable bundle deliberately excludes (see ``bandprepare.spec``).
The tempo is supplied by the user (we do not detect it); see the CLI/GUI knobs.
"""

from __future__ import annotations

import math

import torch

# Click tone: a short sine burst shaped by a fast exponential decay — a clean
# percussive "tick" rather than a sustained beep, and it starts/ends at ~0 so
# there is no pop at the edges. The downbeat (beat 1 of each bar) is pitched
# higher and a touch louder so the count is easy to follow.
_BEAT_FREQ_HZ = 1000.0
_DOWNBEAT_FREQ_HZ = 1500.0
_CLICK_MS = 50.0  # tone-burst length
_DECAY = 18.0  # exponential-decay rate across the burst (≈ silent by the end)
_BEAT_GAIN = 0.6
_DOWNBEAT_GAIN = 0.8


def _click_tone(freq: float, gain: float, samplerate: int, dtype: torch.dtype) -> torch.Tensor:
    """A single decaying sine click as a 1-D ``(samples,)`` tensor."""
    n = max(1, int(round(samplerate * _CLICK_MS / 1000.0)))
    idx = torch.arange(n, dtype=dtype)
    t = idx / samplerate
    env = torch.exp(-_DECAY * idx / n)  # 1 → ~0 across the burst (no end pop)
    return gain * env * torch.sin(2 * math.pi * freq * t)


def click_track(
    bpm: float,
    *,
    samplerate: int,
    bars: int = 1,
    beats_per_bar: int = 4,
    channels: int = 2,
    dtype: torch.dtype = torch.float32,
    device: torch.device | str = "cpu",
) -> torch.Tensor:
    """A count-in click track as ``(channels, samples)``.

    ``bars × beats_per_bar`` evenly spaced clicks at ``bpm``. The track length is
    exactly ``total_beats × beat_duration``, so music concatenated after it lands
    on the very next downbeat: the clicks count "1 2 3 4" and beat 1 of the song
    follows the final click by one beat.
    """
    if bpm <= 0:
        raise ValueError(f"bpm must be positive, got {bpm}")
    if bars < 1 or beats_per_bar < 1:
        raise ValueError(f"bars and beats_per_bar must be >= 1, got {bars}/{beats_per_bar}")

    total_beats = bars * beats_per_bar
    beat_samples = int(round(samplerate * 60.0 / bpm))
    total_samples = beat_samples * total_beats

    track = torch.zeros(total_samples, dtype=dtype, device=device)
    downbeat = _click_tone(_DOWNBEAT_FREQ_HZ, _DOWNBEAT_GAIN, samplerate, dtype).to(device)
    beat = _click_tone(_BEAT_FREQ_HZ, _BEAT_GAIN, samplerate, dtype).to(device)

    for i in range(total_beats):
        tone = downbeat if i % beats_per_bar == 0 else beat
        start = i * beat_samples
        end = min(start + tone.shape[0], total_samples)
        track[start:end] += tone[: end - start]

    return track.unsqueeze(0).repeat(channels, 1)


def prepend_count_in(
    mix: torch.Tensor,
    bpm: float,
    *,
    samplerate: int,
    bars: int = 1,
    beats_per_bar: int = 4,
) -> torch.Tensor:
    """Return ``mix`` (shape ``(channels, samples)``) with a count-in click track
    prepended, matching the mix's channel count, dtype, and device."""
    click = click_track(
        bpm,
        samplerate=samplerate,
        bars=bars,
        beats_per_bar=beats_per_bar,
        channels=mix.shape[0],
        dtype=mix.dtype,
        device=mix.device,
    )
    return torch.cat([click, mix], dim=-1)
