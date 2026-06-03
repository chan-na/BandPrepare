"""LarsNet drum-kit backend.

Splits a ``drums`` stem into five pieces: kick, snare, hihat, cymbals
(crash/ride), toms. The pretrained checkpoints (~562 MB, CC BY-NC 4.0) are
downloaded once from the authors' Google Drive and cached locally.

``torch``/``yaml`` are imported lazily so importing this module (e.g. to read
:data:`DRUM_STEMS` from the registry) stays cheap.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ModelError, SeparationError
from ..logging_utils import get_logger, step
from .base import ModelInfo

if TYPE_CHECKING:  # pragma: no cover - typing only
    import torch

# LarsNet output stems, in display order. (cymbals == crash + ride.) Also the
# source of truth for this model's ``output_stems``.
DRUM_STEMS = ("kick", "snare", "hihat", "cymbals", "toms")

LARSNET_SR = 44100
LARSNET_FT = {"F": 2048, "T": 512}

# Pretrained checkpoints bundle (see LarsNet README).
_GDRIVE_FILE_ID = "1U8-5924B1ii1cjv9p0MTPzayb00P4qoL"
_ZIP_NAME = "pretrained_larsnet_models.zip"


def cache_dir() -> Path:
    base = os.environ.get("BANDPREPARE_CACHE") or os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "bandprepare" / "larsnet"


def _find_checkpoint(root: Path, stem: str) -> Path | None:
    """Locate ``pretrained_<stem>_unet.pth`` regardless of the zip's layout."""
    matches = [
        p for p in root.rglob("*.pth")
        if stem in p.name.lower() and "unet" in p.name.lower()
    ]
    return matches[0] if matches else None


def _all_checkpoints(root: Path) -> dict[str, Path] | None:
    found = {}
    for stem in DRUM_STEMS:
        ckpt = _find_checkpoint(root, stem)
        if ckpt is None:
            return None
        found[stem] = ckpt
    return found


def ensure_checkpoints(verbose: bool = False) -> dict[str, Path]:
    """Return ``{stem: checkpoint_path}``, downloading the bundle if needed."""
    logger = get_logger()
    root = cache_dir()
    root.mkdir(parents=True, exist_ok=True)

    existing = _all_checkpoints(root)
    if existing is not None:
        logger.debug("LarsNet checkpoints already cached at %s", root)
        return existing

    step(logger, f"LarsNet 체크포인트 다운로드 (~562MB, 최초 1회) → {root}")
    step(logger, f"Downloading LarsNet checkpoints (~562MB, first run only)")

    zip_path = root / _ZIP_NAME
    try:
        import gdown

        gdown.download(id=_GDRIVE_FILE_ID, output=str(zip_path), quiet=not verbose)
    except Exception as exc:
        raise ModelError(
            "LarsNet 체크포인트 다운로드에 실패했습니다(네트워크/Google Drive 확인).\n"
            f"  수동 다운로드: https://drive.google.com/uc?id={_GDRIVE_FILE_ID}\n"
            f"  압축을 풀어 {root} 아래에 두면 됩니다.\n"
            f"Failed to download LarsNet checkpoints: {exc}"
        ) from exc

    if not zip_path.exists() or zip_path.stat().st_size < 1_000_000:
        raise ModelError(
            "LarsNet 체크포인트 다운로드가 불완전합니다. 다시 시도하세요. / "
            "LarsNet checkpoint download looks incomplete; please retry."
        )

    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(root)
    except zipfile.BadZipFile as exc:
        raise ModelError(
            f"체크포인트 압축 해제 실패 / Failed to unzip checkpoints: {exc}"
        ) from exc
    finally:
        zip_path.unlink(missing_ok=True)

    found = _all_checkpoints(root)
    if found is None:
        raise ModelError(
            "압축을 풀었지만 5개 체크포인트(kick/snare/hihat/cymbals/toms)를 찾지 못했습니다.\n"
            f"  위치: {root}\n"
            "Could not locate all five LarsNet checkpoints after extraction."
        )
    return found


def _write_config(checkpoints: dict[str, Path]) -> Path:
    """Generate a minimal LarsNet ``config.yaml`` pointing at cached weights."""
    import yaml

    config: dict = {
        "global": {"sr": LARSNET_SR},
        "inference_models": {stem: str(path) for stem, path in checkpoints.items()},
    }
    for stem in DRUM_STEMS:
        config[stem] = dict(LARSNET_FT)

    path = cache_dir() / "config.generated.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(config, f)
    return path


def _run(drums_wav: "torch.Tensor", device: str, wiener_exponent: float | None,
         config_path: Path) -> dict[str, "torch.Tensor"]:
    from ..vendor.larsnet import LarsNet

    net = LarsNet(
        wiener_filter=wiener_exponent is not None,
        wiener_exponent=wiener_exponent if wiener_exponent is not None else 1.0,
        config=str(config_path),
        device=device,
    )
    stems = net(drums_wav.to(device))
    return {stem: wav.detach().cpu() for stem, wav in stems.items()}


def separate(drums_wav: "torch.Tensor", input_sr: int, device: str, *,
             wiener_exponent: float | None = 1.0,
             verbose: bool = False) -> dict[str, "torch.Tensor"]:
    """Split a ``(channels, samples)`` drum stem into per-piece tensors.

    ``wiener_exponent`` enables alpha-Wiener post-filtering to reduce bleed
    between pieces (set to ``None`` to disable). On MPS, LarsNet's complex STFT
    ops may be unsupported; if so we transparently fall back to CPU.
    """
    logger = get_logger()

    if input_sr != LARSNET_SR:
        import torchaudio as ta

        logger.debug("resampling drums %d -> %d for LarsNet", input_sr, LARSNET_SR)
        drums_wav = ta.functional.resample(drums_wav, input_sr, LARSNET_SR)

    checkpoints = ensure_checkpoints(verbose=verbose)
    config_path = _write_config(checkpoints)

    try:
        return _run(drums_wav, device, wiener_exponent, config_path)
    except (NotImplementedError, RuntimeError) as exc:
        if device != "cpu":
            logger.warning(
                "  ! %s 장치에서 드럼 분리에 실패하여 CPU로 대체합니다 / "
                "drum separation failed on %s, falling back to CPU (%s)",
                device, device, exc,
            )
            try:
                return _run(drums_wav, "cpu", wiener_exponent, config_path)
            except Exception as exc2:
                raise SeparationError(
                    f"드럼 세부 분리 실패 / Drum separation failed (cpu fallback): {exc2}"
                ) from exc2
        raise SeparationError(
            f"드럼 세부 분리 실패 / Drum separation failed: {exc}"
        ) from exc


class LarsNetSeparator:
    """Adapter exposing LarsNet through the :class:`Separator` protocol."""

    def __init__(self, info: ModelInfo, device: str, *,
                 wiener_exponent: float | None = 1.0, verbose: bool = False):
        self.info = info
        self._device = device
        self._wiener_exponent = wiener_exponent
        self._verbose = verbose

    def separate(self, wav: "torch.Tensor", input_sr: int, *,
                 progress: bool = True) -> dict[str, "torch.Tensor"]:
        return separate(
            wav, input_sr, self._device,
            wiener_exponent=self._wiener_exponent, verbose=self._verbose,
        )
