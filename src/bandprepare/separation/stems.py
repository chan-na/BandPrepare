"""Demucs instrument-stem backend.

Wraps Demucs' pretrained ``htdemucs`` family. ``htdemucs_6s`` yields six stems
(vocals, drums, bass, guitar, piano, other); ``htdemucs_ft`` yields four
(vocals, drums, bass, other). Weights download automatically on first use and
cache under ``~/.cache/torch``.

``torch`` is imported lazily (inside methods) so importing this module — e.g.
to read :data:`STEM_ORDER` from the registry — does not pull the heavy stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..errors import ModelError, SeparationError
from ..logging_utils import get_logger
from .base import ModelInfo, ProgressFn

if TYPE_CHECKING:  # pragma: no cover - typing only
    import torch

# Canonical display order for htdemucs_6s' stems (independent of the model's own
# source order). Also the source of truth for that model's ``output_stems``.
STEM_ORDER = ("vocals", "drums", "bass", "guitar", "piano", "other")

# htdemucs_ft (and the original 4-source htdemucs) drop guitar/piano.
STEM_ORDER_4 = ("vocals", "drums", "bass", "other")


def load_model(name: str, device: str):
    """Load a Demucs model by name, downloading weights on first run."""
    logger = get_logger()
    try:
        from demucs.pretrained import get_model
    except Exception as exc:  # pragma: no cover
        raise ModelError(f"demucs를 불러올 수 없습니다 / Could not import demucs: {exc}") from exc

    try:
        logger.debug("loading demucs model %s", name)
        model = get_model(name)
    except Exception as exc:
        raise ModelError(
            f"Demucs 모델 '{name}' 가중치를 다운로드/로드하지 못했습니다.\n"
            f"  네트워크 연결을 확인하세요. / Failed to download or load Demucs weights.\n"
            f"  ({exc})"
        ) from exc

    model.to(device)
    model.eval()
    return model


def _estimate_total_chunks(models, length: int, shifts: int, overlap: float) -> int:
    """Expected number of leaf forward passes ``demucs.apply.apply_model`` makes.

    Mirrors its chunking: each (sub)model splits the track into
    ``model.segment``-second segments with ``1 - overlap`` stride, once per
    shift. Each shift pads the track by a random amount up to 0.5 s — estimated
    here at the mean — so the count is approximate; callers must clamp the
    resulting fraction.
    """
    import math

    total = 0
    for m in models:
        segment_length = int(m.samplerate * m.segment)
        stride = max(1, int((1 - overlap) * segment_length))
        est_length = length + (int(0.25 * m.samplerate) if shifts else 0)
        total += max(1, math.ceil(est_length / stride)) * max(1, shifts)
    return total


def apply_demucs(model, wav: "torch.Tensor", device: str, *, shifts: int = 1,
                 overlap: float = 0.25, progress: bool = True,
                 progress_cb: ProgressFn | None = None) -> dict[str, "torch.Tensor"]:
    """Run any Demucs model over a ``(channels, samples)`` mixture.

    Applies Demucs' standard per-track normalization (subtract mean, divide by
    std) before inference and undoes it afterwards. Returns ``{name: tensor}``
    keyed by the model's own ``sources`` (no reordering); callers map/order as
    they see fit. Shared by the instrument-stem and drum (DrumSep) backends.

    demucs 4.0.1's ``apply_model`` has no progress hook (only its own tqdm), so
    ``progress_cb`` is driven by counting leaf forward passes via temporary
    forward hooks against the estimated chunk total.
    """
    import torch
    from demucs.apply import BagOfModels, apply_model

    ref = wav.mean(0)
    mean = ref.mean()
    std = ref.std()
    denom = std if float(std) > 0 else torch.tensor(1.0)

    hooks = []
    if progress_cb is not None:
        leaves = list(model.models) if isinstance(model, BagOfModels) else [model]
        total = _estimate_total_chunks(leaves, wav.shape[-1], shifts, overlap)
        done = 0

        def _count(_module, _inputs, _output) -> None:
            nonlocal done
            done += 1
            progress_cb(min(done / total, 1.0))

        hooks = [m.register_forward_hook(_count) for m in leaves]

    wav_n = (wav - mean) / denom
    try:
        out = apply_model(
            model,
            wav_n[None],
            device=device,
            shifts=shifts,
            split=True,
            overlap=overlap,
            progress=progress,
        )
    except RuntimeError as exc:
        raise SeparationError(
            f"분리 중 오류가 발생했습니다 / Error during Demucs separation: {exc}"
        ) from exc
    finally:
        for h in hooks:
            h.remove()

    sources = out[0] * denom + mean  # (n_sources, channels, samples)
    return {name: sources[i] for i, name in enumerate(model.sources)}


class DemucsSeparator:
    """Adapter exposing a Demucs model through the :class:`Separator` protocol."""

    def __init__(self, info: ModelInfo, device: str, model_name: str, *,
                 shifts: int = 1, overlap: float = 0.25):
        self.info = info
        self._device = device
        self._shifts = shifts
        self._overlap = overlap
        self._model = load_model(model_name, device)

    def separate(self, wav: "torch.Tensor", input_sr: int, *,
                 progress: bool = True,
                 progress_cb: ProgressFn | None = None) -> dict[str, "torch.Tensor"]:
        # The pipeline loads audio at ``info.samplerate`` (== model rate), so no
        # resampling is needed here.
        by_name = apply_demucs(
            self._model, wav, self._device,
            shifts=self._shifts, overlap=self._overlap, progress=progress,
            progress_cb=progress_cb,
        )
        # Present in canonical display order; include any unexpected extras.
        ordered = {name: by_name[name] for name in STEM_ORDER if name in by_name}
        for name, tensor in by_name.items():
            ordered.setdefault(name, tensor)
        return ordered
