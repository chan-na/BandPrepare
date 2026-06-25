"""Fetch audio from a URL (YouTube etc.) via yt-dlp, for use as pipeline input.

The download happens in the entry layer (CLI ``main`` / GUI worker), NOT inside
``pipeline.run`` — the pipeline stays a pure "audio file in → stems out" step, so
this network-dependent code is isolated from the well-tested separation path.

We grab the ``bestaudio`` stream WITHOUT re-encoding: YouTube audio containers
(m4a/webm/opus) are decoded straight through :func:`bandprepare.audio.load_track`'s
bundled-ffmpeg path (no ffprobe needed), so no post-processing is required. The
downloaded file is saved as ``source.<ext>`` next to where the run's outputs go
(``<base>/BandPrepareOutput/<title>/``), so the original stays available for
re-listening / re-processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from . import audio
from .errors import DownloadError
from .logging_utils import get_logger, step

# ``callback(fraction)`` — download progress in [0, 1]; used by the GUI to drive
# its bar. The CLI passes None and lets yt-dlp print its own progress instead.
DownloadProgress = Callable[[float], None]


@dataclass
class FetchResult:
    """Outcome of a successful :func:`fetch`."""

    audio_path: Path   # the downloaded audio file (…/source.<ext>)
    output_dir: Path   # the per-song folder the pipeline should write into
    title: str         # the video/track title (already filename-sanitized by yt-dlp)


def is_url(text: str) -> bool:
    """True if ``text`` looks like an http(s) URL (vs a local file path).

    Used by the CLI to decide whether the positional input is a link to fetch or
    a file to open. Restricting to http/https keeps Windows drive paths
    (``C:\\song.mp3`` → scheme ``c``) and bare filenames out.
    """
    try:
        parsed = urlparse(text.strip())
    except (ValueError, AttributeError):
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _progress_hook(progress_cb: DownloadProgress):
    """Adapt yt-dlp's progress dicts into ``progress_cb(fraction)`` calls."""

    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            got = d.get("downloaded_bytes") or 0
            if total:
                progress_cb(min(got / total, 1.0))
        elif status == "finished":
            progress_cb(1.0)

    return hook


def fetch(
    url: str,
    *,
    dest_base: Path,
    explicit_output: Optional[Path] = None,
    progress_cb: Optional[DownloadProgress] = None,
    verbose: bool = False,
) -> FetchResult:
    """Download ``url``'s best audio to a file and return where it landed.

    The file is named ``source.<ext>`` (yt-dlp fills the real extension). It is
    placed in ``explicit_output`` if given, otherwise in
    ``dest_base / "BandPrepareOutput" / <title>`` — yt-dlp substitutes and
    sanitizes ``<title>`` into the path in a single download, so the per-song
    output folder is discovered from the result (no extra metadata round-trip).
    """
    import yt_dlp  # heavy, dynamically-loaded extractors — import lazily

    logger = get_logger()

    if explicit_output is not None:
        out_tmpl = str(Path(explicit_output) / "source.%(ext)s")
    else:
        out_tmpl = str(
            Path(dest_base) / "BandPrepareOutput" / "%(title)s" / "source.%(ext)s"
        )

    quiet = progress_cb is not None or not verbose
    ydl_opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": out_tmpl,
        "noplaylist": True,       # a watch?...&list=... URL → just the one video
        "restrictfilenames": False,  # keep Unicode (Korean) titles in folder names
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": progress_cb is not None,  # GUI drives its own bar
    }
    if progress_cb is not None:
        ydl_opts["progress_hooks"] = [_progress_hook(progress_cb)]

    # Point yt-dlp at a usable ffmpeg (bundled or system). prepare_ffmpeg_path()
    # is idempotent and exposes a bare-named ffmpeg on PATH; pass its directory so
    # yt-dlp finds it even when only the version-named bundled binary exists.
    ff = audio.prepare_ffmpeg_path()
    if ff:
        ydl_opts["ffmpeg_location"] = str(Path(ff).parent)

    step(logger, f"유튜브/URL 음원 다운로드 / fetching audio → {url}")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:  # yt_dlp.utils.DownloadError and anything else
        raise DownloadError(
            f"URL에서 음원을 받지 못했습니다(링크/네트워크/접근권한 확인). / "
            f"Could not fetch audio from the URL: {exc}\n"
            f"  URL: {url}"
        ) from exc

    # noplaylist still yields a playlist dict for some inputs; take the first entry.
    if info.get("entries"):
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise DownloadError(
                f"URL에 받을 수 있는 음원이 없습니다. / No downloadable audio at URL: {url}"
            )
        info = entries[0]

    audio_path = _resolve_downloaded_path(info)
    if audio_path is None or not audio_path.exists():
        raise DownloadError(
            f"다운로드 파일을 찾을 수 없습니다. / Downloaded file not found for URL: {url}"
        )

    title = info.get("title") or audio_path.parent.name
    return FetchResult(audio_path=audio_path, output_dir=audio_path.parent, title=title)


def _resolve_downloaded_path(info: dict) -> Optional[Path]:
    """Best-effort final-file path from a yt-dlp info dict."""
    downloads = info.get("requested_downloads")
    if downloads:
        fp = downloads[0].get("filepath") or downloads[0].get("_filename")
        if fp:
            return Path(fp)
    fp = info.get("filepath") or info.get("_filename")
    return Path(fp) if fp else None
