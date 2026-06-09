"""Pin the vendored Mel filter bank to librosa's output.

Mel-Band RoFormer's weights depend on the exact shape/values of the mel filter
bank, so the vendored pure-NumPy ``mel()`` (which lets us drop librosa/numba/
llvmlite from the portable bundle — Phase 5b / D6) must match librosa bit-for-
bit at the params the model uses. The librosa comparison skips when librosa is
not installed (the roformer extra no longer pulls it in); a librosa-free sanity
check always runs.
"""

from __future__ import annotations

import numpy as np
import pytest

from bandprepare.vendor.roformer._mel import mel as vendored_mel

# Exact params Mel-Band RoFormer passes (configs/mel_band_vocals_kj.yaml:
# sample_rate=44100, stft_n_fft=2048, num_bands=60). The first entry is the
# load-bearing one; the others guard the helper math more broadly.
PARAM_SETS = [
    dict(sr=44100, n_fft=2048, n_mels=60),
    dict(sr=22050, n_fft=2048, n_mels=128),
    dict(sr=16000, n_fft=1024, n_mels=80),
    dict(sr=48000, n_fft=4096, n_mels=64),
]


@pytest.mark.parametrize("kw", PARAM_SETS, ids=lambda k: f"sr{k['sr']}_nfft{k['n_fft']}_m{k['n_mels']}")
def test_vendored_mel_matches_librosa(kw):
    librosa = pytest.importorskip("librosa")
    expected = librosa.filters.mel(**kw)
    got = vendored_mel(**kw)
    assert got.shape == expected.shape
    assert got.dtype == expected.dtype
    np.testing.assert_allclose(got, expected, rtol=0, atol=0)


def test_vendored_mel_shape_and_properties():
    """librosa-free sanity: the model's exact params yield a sane filter bank."""
    fb = vendored_mel(sr=44100, n_fft=2048, n_mels=60)
    assert fb.shape == (60, 1 + 2048 // 2)
    assert fb.dtype == np.float32
    assert np.all(fb >= 0)
    # Every mel band must cover at least one FFT bin (the model asserts this).
    assert np.all(fb.max(axis=1) > 0)
