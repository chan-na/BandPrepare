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
from .base import ModelInfo

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


def apply_demucs(model, wav: "torch.Tensor", device: str, *, shifts: int = 1,
                 overlap: float = 0.25, progress: bool = True) -> dict[str, "torch.Tensor"]:
    """Run any Demucs model over a ``(channels, samples)`` mixture.

    Applies Demucs' standard per-track normalization (subtract mean, divide by
    std) before inference and undoes it afterwards. Returns ``{name: tensor}``
    keyed by the model's own ``sources`` (no reordering); callers map/order as
    they see fit. Shared by the instrument-stem and drum (DrumSep) backends.
    """
    import torch
    from demucs.apply import apply_model

    ref = wav.mean(0)
    mean = ref.mean()
    std = ref.std()
    denom = std if float(std) > 0 else torch.tensor(1.0)

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
                 progress: bool = True) -> dict[str, "torch.Tensor"]:
        # The pipeline loads audio at ``info.samplerate`` (== model rate), so no
        # resampling is needed here.
        by_name = apply_demucs(
            self._model, wav, self._device,
            shifts=self._shifts, overlap=self._overlap, progress=progress,
        )
        # Present in canonical display order; include any unexpected extras.
        ordered = {name: by_name[name] for name in STEM_ORDER if name in by_name}
        for name, tensor in by_name.items():
            ordered.setdefault(name, tensor)
        return ordered
