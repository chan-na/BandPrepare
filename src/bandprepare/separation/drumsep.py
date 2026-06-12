"""DrumSep (inagoy) drum-kit backend.

A Hybrid Demucs model fine-tuned for drums (4 pieces: kick, snare, toms,
cymbals). Loaded through Demucs' own ``get_model`` from a local repo of one
checkpoint (signature ``49469ca8``), downloaded once from the author's Drive.

Ref: https://github.com/inagoy/drumsep — sources are labelled in Spanish in the
checkpoint (bombo/redoblante/platillos/toms); we map them to canonical English.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ModelError, SeparationError
from ..logging_utils import get_logger
from . import download
from .base import ModelInfo, ProgressFn
from .stems import apply_demucs

if TYPE_CHECKING:  # pragma: no cover - typing only
    import torch

# Canonical pieces this backend emits, in display order.
DRUMSEP_STEMS = ("kick", "snare", "toms", "cymbals")

DRUMSEP_SR = 44100
_GDRIVE_FILE_ID = "1-Dm666ScPkg8Gt2-lK3Ua0xOudWHZBGC"
_SIG = "49469ca8"  # demucs model signature → repo file ``49469ca8.th``

# Map the checkpoint's source labels (Spanish, and English just in case) to our
# canonical names.
_SOURCE_MAP = {
    "bombo": "kick", "kick": "kick",
    "redoblante": "snare", "snare": "snare",
    "toms": "toms", "tom": "toms", "tom-toms": "toms",
    "platillos": "cymbals", "cymbals": "cymbals", "cymbal": "cymbals",
}


def _ensure_repo(verbose: bool = False) -> Path:
    """Return the local Demucs repo dir containing ``49469ca8.th``."""
    repo = download.model_cache_dir("drumsep")
    ckpt = repo / f"{_SIG}.th"
    download.download_gdrive(
        _GDRIVE_FILE_ID, ckpt, what="DrumSep 체크포인트 / DrumSep checkpoint",
        verbose=verbose, min_bytes=1_000_000,
    )
    return repo


def _load_model(device: str, verbose: bool):
    repo = _ensure_repo(verbose)
    try:
        from demucs.pretrained import get_model
    except Exception as exc:  # pragma: no cover
        raise ModelError(f"demucs를 불러올 수 없습니다 / Could not import demucs: {exc}") from exc
    try:
        model = get_model(_SIG, repo=repo)
    except Exception as exc:
        raise ModelError(
            f"DrumSep 모델을 로드하지 못했습니다(체크포인트 손상?). / "
            f"Failed to load DrumSep model: {exc}"
        ) from exc
    model.to(device)
    model.eval()
    return model


def _map_sources(by_name: dict[str, "torch.Tensor"]) -> dict[str, "torch.Tensor"]:
    """Translate raw source names to canonical and order as DRUMSEP_STEMS."""
    logger = get_logger()
    raw_items = list(by_name.items())
    canon: dict[str, "torch.Tensor"] = {}
    for i, (name, tensor) in enumerate(raw_items):
        key = _SOURCE_MAP.get(name.strip().lower())
        if key is None:
            # Positional fallback keeps us working if labels ever change.
            key = DRUMSEP_STEMS[i] if i < len(DRUMSEP_STEMS) else name
            logger.debug("DrumSep: unmapped source %r → %s (positional)", name, key)
        canon[key] = tensor
    return {s: canon[s] for s in DRUMSEP_STEMS if s in canon}


class DrumSepSeparator:
    """Adapter exposing DrumSep through the :class:`Separator` protocol."""

    def __init__(self, info: ModelInfo, device: str, *,
                 shifts: int = 1, overlap: float = 0.25, verbose: bool = False):
        self.info = info
        self._device = device
        self._shifts = shifts
        self._overlap = overlap
        self._model = _load_model(device, verbose)

    def separate(self, wav: "torch.Tensor", input_sr: int, *,
                 progress: bool = True,
                 progress_cb: ProgressFn | None = None) -> dict[str, "torch.Tensor"]:
        if input_sr != DRUMSEP_SR:
            import torchaudio as ta

            get_logger().debug("resampling drums %d -> %d for DrumSep", input_sr, DRUMSEP_SR)
            wav = ta.functional.resample(wav, input_sr, DRUMSEP_SR)

        try:
            by_name = apply_demucs(
                self._model, wav, self._device,
                shifts=self._shifts, overlap=self._overlap, progress=progress,
                progress_cb=progress_cb,
            )
        except SeparationError:
            raise
        except (NotImplementedError, RuntimeError) as exc:
            raise SeparationError(
                f"드럼 세부 분리 실패 / DrumSep separation failed: {exc}"
            ) from exc
        return {s: t.detach().cpu() for s, t in _map_sources(by_name).items()}
