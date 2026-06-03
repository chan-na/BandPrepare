"""Stage 1 — instrument-stem separation with Demucs ``htdemucs_6s``.

Produces six stems: vocals, drums, bass, guitar, piano, other. Weights are
downloaded automatically by Demucs on first use and cached under
``~/.cache/torch``.
"""

from __future__ import annotations

import torch

from ..errors import ModelError, SeparationError
from ..logging_utils import get_logger

MODEL_NAME = "htdemucs_6s"

# Canonical display order for the six stems (independent of model.sources order).
STEM_ORDER = ("vocals", "drums", "bass", "guitar", "piano", "other")


def load_model(device: str):
    """Load the Demucs model, downloading weights on first run."""
    logger = get_logger()
    try:
        from demucs.pretrained import get_model
    except Exception as exc:  # pragma: no cover
        raise ModelError(f"demucs를 불러올 수 없습니다 / Could not import demucs: {exc}") from exc

    try:
        logger.debug("loading demucs model %s", MODEL_NAME)
        model = get_model(MODEL_NAME)
    except Exception as exc:
        raise ModelError(
            f"Demucs 모델 '{MODEL_NAME}' 가중치를 다운로드/로드하지 못했습니다.\n"
            f"  네트워크 연결을 확인하세요. / Failed to download or load Demucs weights.\n"
            f"  ({exc})"
        ) from exc

    model.to(device)
    model.eval()
    return model


def separate(model, wav: torch.Tensor, device: str, *, shifts: int = 1,
             overlap: float = 0.25, progress: bool = True) -> dict[str, torch.Tensor]:
    """Separate a ``(channels, samples)`` mixture into named stems.

    Applies Demucs' standard per-track normalization (subtract mean, divide by
    std) before inference and undoes it afterwards.
    """
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
            f"악기 분리 중 오류가 발생했습니다 / Error during instrument separation: {exc}"
        ) from exc

    sources = out[0] * denom + mean  # (n_sources, channels, samples)

    by_name = {name: sources[i] for i, name in enumerate(model.sources)}
    # Return in canonical order where possible.
    ordered = {name: by_name[name] for name in STEM_ORDER if name in by_name}
    for name, tensor in by_name.items():  # include any unexpected extras
        ordered.setdefault(name, tensor)
    return ordered
