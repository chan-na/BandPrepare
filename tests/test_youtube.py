"""Tests for URL/YouTube input (bandprepare.youtube) and CLI URL routing.

yt_dlp is replaced with a fake module so these stay fast and network-free. The
fake honours the real ``outtmpl`` (substituting %(title)s/%(ext)s) and writes a
small file, so the path-resolution + output-dir logic is exercised for real.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from bandprepare import youtube
from bandprepare.errors import EXIT_DOWNLOAD, DownloadError


# --- is_url ----------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "https://www.youtube.com/watch?v=abc",
    "http://youtu.be/abc",
    "https://example.com/song",
    "  https://youtu.be/abc  ",  # surrounding whitespace tolerated
])
def test_is_url_true(text):
    assert youtube.is_url(text)


@pytest.mark.parametrize("text", [
    "song.mp3",
    "/music/song.wav",
    "C:\\music\\song.mp3",   # Windows drive path → scheme 'c', not http(s)
    "",
    "ftp://host/file",        # only http/https count as fetchable
    "youtube.com/watch",      # no scheme
])
def test_is_url_false(text):
    assert not youtube.is_url(text)


# --- fetch (fake yt_dlp) ---------------------------------------------------


class _FakeYDL:
    """Minimal yt_dlp.YoutubeDL stand-in honouring outtmpl + writing a file."""

    last_opts: dict | None = None
    title = "My Song"
    ext = "m4a"

    def __init__(self, opts):
        type(self).last_opts = opts
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        for hook in self.opts.get("progress_hooks") or []:
            hook({"status": "downloading", "downloaded_bytes": 5, "total_bytes": 10})
            hook({"status": "finished"})
        filepath = (
            self.opts["outtmpl"]
            .replace("%(title)s", self.title)
            .replace("%(ext)s", self.ext)
        )
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_bytes(b"\x00" * 16)
        return {"title": self.title, "requested_downloads": [{"filepath": filepath}]}


def _install_fake_ytdlp(monkeypatch, ydl_cls=_FakeYDL):
    fake = types.ModuleType("yt_dlp")
    fake.YoutubeDL = ydl_cls
    monkeypatch.setitem(sys.modules, "yt_dlp", fake)
    # Don't touch the real ffmpeg shim during unit tests.
    monkeypatch.setattr(youtube.audio, "prepare_ffmpeg_path", lambda: None)


def test_fetch_auto_output_dir_from_title(tmp_path, monkeypatch):
    _install_fake_ytdlp(monkeypatch)
    res = youtube.fetch("https://youtu.be/x", dest_base=tmp_path, explicit_output=None)

    expected_dir = tmp_path / "BandPrepareOutput" / "My Song"
    assert res.output_dir == expected_dir
    assert res.audio_path == expected_dir / "source.m4a"
    assert res.audio_path.exists()
    assert res.title == "My Song"
    # Core download knobs are set as designed.
    assert _FakeYDL.last_opts["format"] == "bestaudio/best"
    assert _FakeYDL.last_opts["noplaylist"] is True


def test_fetch_explicit_output_dir(tmp_path, monkeypatch):
    _install_fake_ytdlp(monkeypatch)
    out = tmp_path / "chosen"
    res = youtube.fetch("https://youtu.be/x", dest_base=tmp_path, explicit_output=out)
    assert res.output_dir == out
    assert res.audio_path == out / "source.m4a"


def test_fetch_passes_ffmpeg_location(tmp_path, monkeypatch):
    _install_fake_ytdlp(monkeypatch)
    monkeypatch.setattr(youtube.audio, "prepare_ffmpeg_path", lambda: "/x/bin/ffmpeg")
    youtube.fetch("https://youtu.be/x", dest_base=tmp_path)
    assert _FakeYDL.last_opts["ffmpeg_location"] == str(Path("/x/bin/ffmpeg").parent)


def test_fetch_forwards_download_progress(tmp_path, monkeypatch):
    _install_fake_ytdlp(monkeypatch)
    seen: list[float] = []
    youtube.fetch("https://youtu.be/x", dest_base=tmp_path, progress_cb=seen.append)
    assert seen[0] == pytest.approx(0.5)
    assert seen[-1] == 1.0


def test_fetch_wraps_errors_as_download_error(tmp_path, monkeypatch):
    class _BoomYDL(_FakeYDL):
        def extract_info(self, url, download=True):
            raise RuntimeError("boom")

    _install_fake_ytdlp(monkeypatch, _BoomYDL)
    with pytest.raises(DownloadError) as exc:
        youtube.fetch("https://youtu.be/x", dest_base=tmp_path)
    assert exc.value.exit_code == EXIT_DOWNLOAD


def test_fetch_missing_file_raises(tmp_path, monkeypatch):
    class _NoFileYDL(_FakeYDL):
        def extract_info(self, url, download=True):
            return {"title": "X", "requested_downloads": [{"filepath": str(tmp_path / "nope.m4a")}]}

    _install_fake_ytdlp(monkeypatch, _NoFileYDL)
    with pytest.raises(DownloadError):
        youtube.fetch("https://youtu.be/x", dest_base=tmp_path)


# --- CLI routing -----------------------------------------------------------


def test_cli_routes_url_to_fetch_then_run(tmp_path, monkeypatch):
    from bandprepare import cli

    monkeypatch.setattr(cli, "prepare_ffmpeg_path", lambda: None)

    seen = {}

    def fake_fetch(url, *, dest_base, explicit_output, verbose):
        seen["url"] = url
        seen["explicit_output"] = explicit_output
        audio_file = tmp_path / "BandPrepareOutput" / "T" / "source.m4a"
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"x")
        return youtube.FetchResult(audio_file, audio_file.parent, "T")

    captured = {}

    def fake_run(opts):
        captured["opts"] = opts
        return 0

    monkeypatch.setattr(cli.youtube, "fetch", fake_fetch)
    monkeypatch.setattr(cli, "run", fake_run)

    rc = cli.main(["https://youtu.be/abc", "--stems", "vocals"])
    assert rc == 0
    assert seen["url"] == "https://youtu.be/abc"
    assert seen["explicit_output"] is None  # no -o given
    opts = captured["opts"]
    assert opts.input_path == tmp_path / "BandPrepareOutput" / "T" / "source.m4a"
    assert opts.output_dir == tmp_path / "BandPrepareOutput" / "T"


def test_cli_url_with_explicit_output(tmp_path, monkeypatch):
    from bandprepare import cli

    monkeypatch.setattr(cli, "prepare_ffmpeg_path", lambda: None)
    seen = {}

    def fake_fetch(url, *, dest_base, explicit_output, verbose):
        seen["explicit_output"] = explicit_output
        audio_file = Path(explicit_output) / "source.m4a"
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b"x")
        return youtube.FetchResult(audio_file, audio_file.parent, "T")

    monkeypatch.setattr(cli.youtube, "fetch", fake_fetch)
    monkeypatch.setattr(cli, "run", lambda opts: 0)

    out = tmp_path / "out"
    rc = cli.main(["https://youtu.be/abc", "-o", str(out)])
    assert rc == 0
    assert seen["explicit_output"] == out


def test_cli_download_error_returns_exit_code(tmp_path, monkeypatch):
    from bandprepare import cli

    monkeypatch.setattr(cli, "prepare_ffmpeg_path", lambda: None)

    def boom(url, *, dest_base, explicit_output, verbose):
        raise DownloadError("nope / nope")

    monkeypatch.setattr(cli.youtube, "fetch", boom)
    # run() must never be reached.
    monkeypatch.setattr(cli, "run", lambda opts: pytest.fail("run() should not run"))

    rc = cli.main(["https://youtu.be/abc"])
    assert rc == EXIT_DOWNLOAD
