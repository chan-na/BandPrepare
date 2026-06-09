"""Vendored ``librosa.filters.mel`` (pure NumPy) for Mel-Band RoFormer.

``mel_band_roformer.py`` only needs the Mel filter bank from librosa
(``filters.mel(sr=..., n_fft=..., n_mels=...)``). Importing ``librosa`` for that
one call drags in the numba/llvmlite JIT stack, which is awkward to freeze into
the portable PyInstaller bundle (see PORTABLE-GUI-ROADMAP.md decision D6 / Phase
5b). ``librosa.filters.mel`` and its helpers are pure NumPy, so we vendor them
here verbatim to drop librosa/numba/llvmlite entirely.

Source: librosa 0.11.0 (``librosa/filters.py``, ``librosa/core/convert.py``).
Faithfulness is pinned by ``tests/test_mel_filter.py``, which asserts
``np.allclose`` against the installed ``librosa.filters.mel`` for the exact
params the model uses (sr=44100, n_fft=2048, n_mels=60). The ``norm`` numeric
path (which would need ``librosa.util.normalize``) is intentionally omitted; the
model uses the default ``norm="slaney"`` only.
"""

from __future__ import annotations

import warnings
from typing import Optional, Union

import numpy as np


def hz_to_mel(frequencies, *, htk: bool = False):
    """Convert Hz to Mels (librosa 0.11.0)."""
    frequencies = np.asanyarray(frequencies)

    if htk:
        return 2595.0 * np.log10(1.0 + frequencies / 700.0)

    # Fill in the linear part
    f_min = 0.0
    f_sp = 200.0 / 3

    mels = (frequencies - f_min) / f_sp

    # Fill in the log-scale part
    min_log_hz = 1000.0  # beginning of log region (Hz)
    min_log_mel = (min_log_hz - f_min) / f_sp  # same (Mels)
    logstep = np.log(6.4) / 27.0  # step size for log region

    if frequencies.ndim:
        # If we have array data, vectorize
        log_t = frequencies >= min_log_hz
        mels[log_t] = min_log_mel + np.log(frequencies[log_t] / min_log_hz) / logstep
    elif frequencies >= min_log_hz:
        # If we have scalar data, check directly
        mels = min_log_mel + np.log(frequencies / min_log_hz) / logstep

    return mels


def mel_to_hz(mels, *, htk: bool = False):
    """Convert mel bin numbers to frequencies (librosa 0.11.0)."""
    mels = np.asanyarray(mels)

    if htk:
        return 700.0 * (10.0 ** (mels / 2595.0) - 1.0)

    # Fill in the linear scale
    f_min = 0.0
    f_sp = 200.0 / 3
    freqs = f_min + f_sp * mels

    # And now the nonlinear scale
    min_log_hz = 1000.0  # beginning of log region (Hz)
    min_log_mel = (min_log_hz - f_min) / f_sp  # same (Mels)
    logstep = np.log(6.4) / 27.0  # step size for log region

    if mels.ndim:
        # If we have vector data, vectorize
        log_t = mels >= min_log_mel
        freqs[log_t] = min_log_hz * np.exp(logstep * (mels[log_t] - min_log_mel))
    elif mels >= min_log_mel:
        # If we have scalar data, check directly
        freqs = min_log_hz * np.exp(logstep * (mels - min_log_mel))

    return freqs


def fft_frequencies(*, sr: float = 22050, n_fft: int = 2048) -> np.ndarray:
    """Alternative interface for ``np.fft.rfftfreq`` (librosa 0.11.0)."""
    return np.fft.rfftfreq(n=n_fft, d=1.0 / sr)


def mel_frequencies(
    n_mels: int = 128, *, fmin: float = 0.0, fmax: float = 11025.0, htk: bool = False
) -> np.ndarray:
    """Acoustic frequencies tuned to the mel scale (librosa 0.11.0)."""
    # 'Center freqs' of mel bands - uniformly spaced between limits
    min_mel = hz_to_mel(fmin, htk=htk)
    max_mel = hz_to_mel(fmax, htk=htk)

    mels = np.linspace(min_mel, max_mel, n_mels)

    return mel_to_hz(mels, htk=htk)


def mel(
    *,
    sr: float,
    n_fft: int,
    n_mels: int = 128,
    fmin: float = 0.0,
    fmax: Optional[float] = None,
    htk: bool = False,
    norm: Optional[Union[str, float]] = "slaney",
    dtype=np.float32,
) -> np.ndarray:
    """Create a Mel filter-bank (librosa 0.11.0, slaney-norm path only).

    Drop-in for ``librosa.filters.mel`` for the params Mel-Band RoFormer uses.
    Only ``norm="slaney"`` (the default) and ``norm=None`` are supported; the
    numeric-norm path (``librosa.util.normalize``) is intentionally not vendored.
    """
    if fmax is None:
        fmax = float(sr) / 2

    # Initialize the weights
    n_mels = int(n_mels)
    weights = np.zeros((n_mels, int(1 + n_fft // 2)), dtype=dtype)

    # Center freqs of each FFT bin
    fftfreqs = fft_frequencies(sr=sr, n_fft=n_fft)

    # 'Center freqs' of mel bands - uniformly spaced between limits
    mel_f = mel_frequencies(n_mels + 2, fmin=fmin, fmax=fmax, htk=htk)

    fdiff = np.diff(mel_f)
    ramps = np.subtract.outer(mel_f, fftfreqs)

    for i in range(n_mels):
        # lower and upper slopes for all bins
        lower = -ramps[i] / fdiff[i]
        upper = ramps[i + 2] / fdiff[i + 1]

        # .. then intersect them with each other and zero
        weights[i] = np.maximum(0, np.minimum(lower, upper))

    if isinstance(norm, str):
        if norm == "slaney":
            # Slaney-style mel is scaled to be approx constant energy per channel
            enorm = 2.0 / (mel_f[2 : n_mels + 2] - mel_f[:n_mels])
            weights *= enorm[:, np.newaxis]
        else:
            raise ValueError(f"Unsupported norm={norm}")
    elif norm is not None:
        # The numeric-norm path uses librosa.util.normalize, which we do not
        # vendor (the model only ever uses the default norm="slaney").
        raise NotImplementedError(
            "vendored mel() only supports norm='slaney' or norm=None"
        )

    # Only check weights if f_mel[0] is positive
    if not np.all((mel_f[:-2] == 0) | (weights.max(axis=1) > 0)):
        # This means we have an empty channel somewhere
        warnings.warn(
            "Empty filters detected in mel frequency basis. "
            "Some channels will produce empty responses. "
            "Try increasing your sampling rate (and fmax) or "
            "reducing n_mels.",
            stacklevel=2,
        )

    return weights
