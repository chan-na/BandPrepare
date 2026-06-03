"""Shared weight download + cache helpers.

All model weights live under ``<cache>/bandprepare/<model>/`` where ``<cache>``
honours ``BANDPREPARE_CACHE`` then ``XDG_CACHE_HOME`` then ``~/.cache``. This
generalizes the original LarsNet-only logic so every backend caches the same way.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import ModelError
from ..logging_utils import get_logger, step


def cache_root() -> Path:
    base = os.environ.get("BANDPREPARE_CACHE") or os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "bandprepare"


def model_cache_dir(name: str) -> Path:
    """Return (creating) ``<cache>/bandprepare/<name>/``."""
    d = cache_root() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def download_url(url: str, dest: Path, *, what: str,
                 verbose: bool = False, min_bytes: int = 1_000_000) -> Path:
    """Download ``url`` to ``dest`` (cached, idempotent). Follows redirects."""
    import urllib.request

    logger = get_logger()
    if dest.exists() and dest.stat().st_size >= min_bytes:
        logger.debug("%s already cached at %s", what, dest)
        return dest

    step(logger, f"{what} 다운로드 / downloading (first run only) → {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bandprepare"})
        with urllib.request.urlopen(req) as resp, open(tmp, "wb") as out:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        tmp.replace(dest)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise ModelError(
            f"{what} 다운로드 실패(네트워크 확인). / Failed to download {what}: {exc}\n"
            f"  URL: {url}\n  저장 위치 / save to: {dest}"
        ) from exc

    if not dest.exists() or dest.stat().st_size < min_bytes:
        raise ModelError(
            f"{what} 다운로드가 불완전합니다. 다시 시도하세요. / "
            f"{what} download looks incomplete; please retry."
        )
    return dest


def download_gdrive(file_id: str, dest: Path, *, what: str,
                    verbose: bool = False, min_bytes: int = 1_000_000) -> Path:
    """Download a single Google-Drive file to ``dest`` (cached, idempotent)."""
    logger = get_logger()
    if dest.exists() and dest.stat().st_size >= min_bytes:
        logger.debug("%s already cached at %s", what, dest)
        return dest

    step(logger, f"{what} 다운로드 / downloading (first run only) → {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        import gdown

        gdown.download(id=file_id, output=str(dest), quiet=not verbose)
    except Exception as exc:
        raise ModelError(
            f"{what} 다운로드 실패(네트워크/Google Drive 확인).\n"
            f"  수동 다운로드: https://drive.google.com/uc?id={file_id}\n"
            f"  저장 위치: {dest}\n"
            f"Failed to download {what}: {exc}"
        ) from exc

    if not dest.exists() or dest.stat().st_size < min_bytes:
        raise ModelError(
            f"{what} 다운로드가 불완전합니다. 다시 시도하세요. / "
            f"{what} download looks incomplete; please retry."
        )
    return dest
