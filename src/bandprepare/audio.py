"""Audio loading / saving and environment checks.

Decoding of compressed inputs (mp3, m4a, ...) goes through ffmpeg via Demucs'
``AudioFile``; we keep a torchaudio fallback for formats it can read directly
(e.g. wav/flac). Saving reuses Demucs' encoder so wav/mp3/flac all work with one
code path.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import torch

from .errors import DependencyError, InputError
from .logging_utils import get_logger

SUPPORTED_FORMATS = ("wav", "mp3", "flac")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def ensure_ffmpeg() -> None:
    """Fail early with an actionable message if ffmpeg is not on PATH."""
    if ffmpeg_available():
        return
    raise DependencyError(
        "ffmpeg를 찾을 수 없습니다. mp3/m4a 등 디코딩에 필요합니다.\n"
        "  설치: macOS `brew install ffmpeg`, Ubuntu `sudo apt install ffmpeg`.\n"
        "ffmpeg was not found on PATH; it is required to decode mp3/m4a/etc."
    )


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

    wav = None
    ffmpeg_error: str | None = None
    try:
        wav = AudioFile(path).read(streams=0, samplerate=samplerate, channels=channels)
    except FileNotFoundError:
        # AudioFile shells out to ffmpeg; FileNotFoundError == ffmpeg missing.
        ffmpeg_error = "ffmpeg not found"
    except subprocess.CalledProcessError as exc:
        ffmpeg_error = f"ffmpeg failed ({exc})"
    except Exception as exc:  # pragma: no cover - defensive
        ffmpeg_error = str(exc)

    if wav is None:
        logger.debug("ffmpeg decode unavailable/failed (%s); trying torchaudio", ffmpeg_error)
        try:
            import torchaudio as ta

            loaded, sr = ta.load(str(path))
        except Exception as exc:
            raise InputError(
                f"오디오 파일을 디코딩할 수 없습니다: {path}\n"
                f"  ffmpeg: {ffmpeg_error}; torchaudio: {exc}\n"
                f"Could not decode audio file: {path}"
            ) from exc
        wav = convert_audio(loaded, sr, samplerate, channels)

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
