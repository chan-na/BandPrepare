"""Audio loading / saving and environment checks.

Decoding of compressed inputs (mp3, m4a, ...) needs ffmpeg. We resolve it from
the system PATH or — for a fully portable install — from the pip-bundled static
binary shipped by ``imageio-ffmpeg`` (see :func:`resolve_ffmpeg`). Demucs'
``AudioFile`` is tried first (it also needs ``ffprobe``); when only the bundle is
available we decode through ffmpeg directly (no ffprobe). A torchaudio fallback
covers formats readable without any ffmpeg (e.g. wav/flac). Saving reuses Demucs'
encoder so wav/mp3/flac all work with one code path.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import torch

from .errors import DependencyError, InputError
from .logging_utils import get_logger

SUPPORTED_FORMATS = ("wav", "mp3", "flac")


def _bundled_ffmpeg_exe() -> str | None:
    """Path to the pip-bundled static ffmpeg (``imageio-ffmpeg``), or ``None``.

    The bundle ships ffmpeg only — no ffprobe — under a version-suffixed filename
    (e.g. ``ffmpeg-macos-x86_64-v7.1``), so it satisfies decoding but not the
    bare-``ffmpeg``/``ffprobe`` PATH lookups that some libraries (Demucs) perform.
    """
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    return exe if exe and Path(exe).exists() else None


def resolve_ffmpeg() -> str | None:
    """Best available ffmpeg executable: system ``ffmpeg``, else the bundled one."""
    return shutil.which("ffmpeg") or _bundled_ffmpeg_exe()


def ffmpeg_available() -> bool:
    return resolve_ffmpeg() is not None


def ensure_ffmpeg() -> None:
    """Fail early with an actionable message if no ffmpeg is available."""
    if ffmpeg_available():
        return
    raise DependencyError(
        "ffmpeg를 찾을 수 없습니다. mp3/m4a 등 디코딩에 필요합니다.\n"
        "  설치: macOS `brew install ffmpeg`, Ubuntu `sudo apt install ffmpeg`,\n"
        "  또는 동봉 ffmpeg 사용을 위해 `pip install imageio-ffmpeg`.\n"
        "ffmpeg was not found (neither on PATH nor bundled via imageio-ffmpeg); "
        "it is required to decode mp3/m4a/etc."
    )


_ffmpeg_path_prepared = False


def prepare_ffmpeg_path() -> str | None:
    """Make a bare ``ffmpeg`` resolvable on ``PATH`` (idempotent app-startup hook).

    Call this once from the CLI/GUI entry point. If the system already provides
    ``ffmpeg`` on PATH this is a no-op. Otherwise the bundled (imageio-ffmpeg)
    binary — which has a version-suffixed filename — is linked to ``ffmpeg`` in a
    small shim directory under the cache, and that directory is prepended to
    ``PATH`` so libraries that shell out by bare name resolve it.

    The bundle ships no ``ffprobe``; compressed-input decoding therefore relies on
    :func:`load_track`'s direct-ffmpeg path, which does not need ffprobe. Returns
    the ffmpeg path now resolvable on PATH, or ``None`` if none exists.
    """
    global _ffmpeg_path_prepared
    if _ffmpeg_path_prepared or shutil.which("ffmpeg"):
        _ffmpeg_path_prepared = True
        return shutil.which("ffmpeg")
    _ffmpeg_path_prepared = True

    bundled = _bundled_ffmpeg_exe()
    if not bundled:
        return None

    from .separation.download import cache_root

    shim = cache_root() / "ffmpeg-bin"
    shim.mkdir(parents=True, exist_ok=True)
    link = shim / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(bundled)
    except OSError:
        # e.g. Windows without symlink privilege — copy the binary instead.
        shutil.copy2(bundled, link)
    os.environ["PATH"] = str(shim) + os.pathsep + os.environ.get("PATH", "")
    return shutil.which("ffmpeg")


def _decode_with_ffmpeg(path: Path, channels: int, samplerate: int, exe: str) -> torch.Tensor:
    """Decode any ffmpeg-readable file to ``(channels, samples)`` using ``exe``.

    Uses ffmpeg only (no ffprobe): ffmpeg emits interleaved ``f32le`` PCM at the
    target samplerate/channels on stdout, which we reshape. This is the path taken
    when only the bundled ffmpeg is available (e.g. a frozen app), since Demucs'
    ``AudioFile`` additionally needs ffprobe to read stream metadata.
    """
    import numpy as np

    cmd = [
        exe, "-y", "-loglevel", "error",
        "-i", str(path),
        "-f", "f32le",
        "-ac", str(channels), "-ar", str(samplerate),
        "-threads", "1", "pipe:1",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip() or f"exit {proc.returncode}"
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=detail)
    arr = np.frombuffer(proc.stdout, dtype=np.float32)
    if arr.size < channels:
        raise InputError(
            f"오디오에 샘플이 없습니다(빈 파일?): {path} / Decoded audio is empty: {path}"
        )
    frames = arr.size // channels
    wav = arr[: frames * channels].reshape(frames, channels).T  # (channels, samples)
    return torch.from_numpy(np.ascontiguousarray(wav))


def validate_input(path: Path) -> Path:
    path = Path(path).expanduser()
    if not path.exists():
        raise InputError(
            f"입력 파일을 찾을 수 없습니다: {path} / Input file not found: {path}"
        )
    if not path.is_file():
        raise InputError(
            f"입력 경로가 파일이 아닙니다: {path} / Input path is not a file: {path}"
        )
    return path


def load_track(path: Path, channels: int, samplerate: int) -> torch.Tensor:
    """Decode ``path`` to a float tensor of shape ``(channels, samples)``.

    Mirrors Demucs' own loading logic but raises our bilingual error types so
    the CLI can map them to clean exit codes.
    """
    from demucs.audio import AudioFile, convert_audio

    logger = get_logger()
    path = Path(path)

    tried: list[str] = []
    wav = None

    # 1) Demucs AudioFile — handles any format, but needs system ffmpeg AND
    #    ffprobe (the latter for stream metadata).
    try:
        wav = AudioFile(path).read(streams=0, samplerate=samplerate, channels=channels)
    except FileNotFoundError:
        # AudioFile shells out to ffmpeg/ffprobe; FileNotFoundError == missing.
        tried.append("system ffmpeg/ffprobe not found")
    except subprocess.CalledProcessError as exc:
        tried.append(f"ffmpeg failed ({exc})")
    except Exception as exc:  # pragma: no cover - defensive
        tried.append(f"demucs AudioFile: {exc}")

    # 2) ffmpeg binary directly (no ffprobe) — the bundled / no-system-ffmpeg path.
    if wav is None:
        exe = resolve_ffmpeg()
        if exe:
            logger.debug("AudioFile path failed; decoding via ffmpeg binary %s", exe)
            try:
                wav = _decode_with_ffmpeg(path, channels, samplerate, exe)
            except Exception as exc:
                tried.append(f"ffmpeg decode: {exc}")
        else:
            tried.append("no ffmpeg binary available")

    # 3) torchaudio — formats readable without any ffmpeg (e.g. wav/flac).
    if wav is None:
        try:
            import torchaudio as ta

            loaded, sr = ta.load(str(path))
            wav = convert_audio(loaded, sr, samplerate, channels)
        except Exception as exc:
            tried.append(f"torchaudio: {exc}")

    if wav is None:
        raise InputError(
            f"오디오 파일을 디코딩할 수 없습니다: {path}\n"
            f"  시도 / tried: {'; '.join(tried)}\n"
            f"Could not decode audio file: {path}"
        )

    if wav.numel() == 0:
        raise InputError(
            f"오디오에 샘플이 없습니다(빈 파일?): {path} / Decoded audio is empty: {path}"
        )
    return wav


def save_waveform(wav: torch.Tensor, path: Path, samplerate: int, fmt: str) -> Path:
    """Write ``wav`` (shape ``(channels, samples)``) to ``path`` in ``fmt``."""
    from demucs.audio import save_audio

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict = {}
    if fmt == "mp3":
        kwargs["bitrate"] = 320
    elif fmt in ("wav", "flac"):
        kwargs["bits_per_sample"] = 16

    save_audio(wav.cpu(), str(path), samplerate=samplerate, **kwargs)
    return path
