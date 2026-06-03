"""Generate a short synthetic multi-instrument clip for demos and tests.

This is NOT real music — it is a deterministic mix of a bass line, a simple
drum pattern (kick/snare/hihat), and a melodic tone. It is enough to exercise
the full pipeline end-to-end quickly; for real separation quality use an actual
song.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def _adsr(n: int, sr: int, attack=0.005, release=0.12) -> np.ndarray:
    env = np.ones(n)
    a = min(int(attack * sr), n)
    r = min(int(release * sr), n - a)  # keep attack + release within the buffer
    if a > 0:
        env[:a] = np.linspace(0, 1, a)
    if r > 0:
        env[-r:] = np.linspace(1, 0, r)
    return env


def _tone(freq: float, n: int, sr: int, harmonics=(1.0, 0.3, 0.15)) -> np.ndarray:
    t = np.arange(n) / sr
    wave = np.zeros(n)
    for i, amp in enumerate(harmonics, start=1):
        wave += amp * np.sin(2 * np.pi * freq * i * t)
    return wave * _adsr(n, sr)


def _noise_burst(n: int, sr: int, highpass=False) -> np.ndarray:
    rng = np.random.default_rng(0 if highpass else 1)
    x = rng.standard_normal(n)
    # crude one-pole filter to shape kick/snare vs hihat
    y = np.zeros(n)
    a = 0.9 if highpass else 0.5
    for i in range(1, n):
        y[i] = a * y[i - 1] + (x[i] - x[i - 1] if highpass else x[i])
    return y / (np.max(np.abs(y)) + 1e-9) * _adsr(n, sr, release=0.05 if highpass else 0.15)


def make_sample(path: Path, seconds: float = 6.0, sr: int = 44100, bpm: float = 100.0) -> Path:
    n = int(seconds * sr)
    beat = 60.0 / bpm
    bass = np.zeros(n)
    drums = np.zeros(n)
    melody = np.zeros(n)

    # Bass line: root notes on each beat.
    bass_freqs = [55.0, 55.0, 73.42, 65.41]  # A1, A1, D2, C2
    for b in range(int(seconds / beat)):
        start = int(b * beat * sr)
        dur = int(beat * sr)
        end = min(start + dur, n)
        f = bass_freqs[b % len(bass_freqs)]
        bass[start:end] += _tone(f, end - start, sr, harmonics=(1.0, 0.5, 0.25)) * 0.6

    # Drums: kick on beats, snare on backbeats, hihat on eighths.
    eighth = beat / 2
    for k in range(int(seconds / eighth)):
        start = int(k * eighth * sr)
        # hihat every eighth
        h = _noise_burst(int(0.05 * sr), sr, highpass=True) * 0.15
        drums[start:min(start + len(h), n)] += h[: max(0, min(len(h), n - start))]
        if k % 2 == 0:  # downbeats -> kick
            kd = _tone(60.0, int(0.18 * sr), sr, harmonics=(1.0,)) * 0.9
            drums[start:min(start + len(kd), n)] += kd[: max(0, min(len(kd), n - start))]
        if k % 4 == 2:  # backbeat -> snare
            sn = _noise_burst(int(0.12 * sr), sr) * 0.5
            drums[start:min(start + len(sn), n)] += sn[: max(0, min(len(sn), n - start))]

    # Melody: simple arpeggio on top.
    mel_freqs = [440.0, 554.37, 659.25, 554.37]  # A4, C#5, E5, C#5
    for m in range(int(seconds / beat)):
        start = int(m * beat * sr)
        dur = int(beat * 0.9 * sr)
        end = min(start + dur, n)
        f = mel_freqs[m % len(mel_freqs)]
        melody[start:end] += _tone(f, end - start, sr, harmonics=(1.0, 0.2)) * 0.25

    mono = bass + drums + melody
    mono /= np.max(np.abs(mono)) + 1e-9
    mono *= 0.9
    # Slight stereo width.
    stereo = np.stack([mono, np.roll(mono, 5)], axis=1).astype(np.float32)

    import soundfile as sf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), stereo, sr)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a synthetic test clip.")
    parser.add_argument("-o", "--output", default="assets/sample.wav")
    parser.add_argument("--seconds", type=float, default=6.0)
    args = parser.parse_args()
    out = make_sample(Path(args.output), seconds=args.seconds)
    print(f"wrote {out}")
