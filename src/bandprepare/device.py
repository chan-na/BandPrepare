"""Compute-device resolution for ``--device {auto,cpu,cuda,mps}``."""

from __future__ import annotations

import platform

import torch

from .errors import DependencyError
from .logging_utils import get_logger

VALID_CHOICES = ("auto", "cpu", "cuda", "mps")


def _cuda_ok() -> bool:
    return torch.cuda.is_available()


def _mps_ok() -> bool:
    return torch.backends.mps.is_available()


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def resolve_device(choice: str) -> str:
    """Turn the user's ``--device`` choice into a concrete torch device string.

    ``auto`` prefers CUDA, then Apple-Silicon MPS, then CPU. On Intel Macs the
    Metal/AMD MPS path is available but routinely *slower* than CPU (and can
    stall) for these models, so ``auto`` deliberately skips it there. Users can
    still force it with an explicit ``--device mps``. An explicit choice that is
    unavailable is an error rather than a silent downgrade, so the user is never
    surprised by a slow run they did not ask for.
    """
    logger = get_logger()
    choice = (choice or "auto").lower()
    if choice not in VALID_CHOICES:
        raise DependencyError(
            f"알 수 없는 device '{choice}'. {VALID_CHOICES} 중 하나여야 합니다. / "
            f"Unknown device '{choice}'; must be one of {VALID_CHOICES}."
        )

    if choice == "auto":
        if _cuda_ok():
            device = "cuda"
        elif _mps_ok() and _is_apple_silicon():
            device = "mps"
        else:
            if _mps_ok() and not _is_apple_silicon():
                logger.debug("MPS is available but this is not Apple Silicon; "
                             "auto prefers CPU (use --device mps to force).")
            device = "cpu"
        logger.debug("device=auto resolved to %s", device)
        return device

    if choice == "cuda" and not _cuda_ok():
        raise DependencyError(
            "CUDA를 사용할 수 없습니다(GPU/드라이버 확인). / CUDA is not available on this machine."
        )
    if choice == "mps" and not _mps_ok():
        raise DependencyError(
            "MPS(Apple/Metal)를 사용할 수 없습니다. / MPS (Apple/Metal) backend is not available."
        )
    return choice
