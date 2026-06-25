"""Background separation worker.

Runs ``pipeline.run`` on a ``QThread`` so the UI stays responsive. The worker
NEVER touches widgets; it only emits signals, which Qt marshals back to the GUI
thread via queued connections. The pipeline's progress callback fires on this
worker thread, so it too is forwarded purely through a signal.

For URL inputs (``Options.source_url``) the worker first downloads the audio on
this background thread, then runs the normal pipeline over the saved file — so
the (network-bound, possibly slow) fetch never blocks the UI.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .. import pipeline, youtube
from ..cli import portable_base
from ..errors import BandPrepareError

# Fraction of the overall progress bar reserved for the URL download; the
# separation pipeline then shares the remaining [_DOWNLOAD_BAR_SHARE, 1.0].
_DOWNLOAD_BAR_SHARE = 0.10


def _scale_pipeline_fraction(frac, *, fetched: bool):
    """Map a pipeline fraction onto the bar, leaving room for a prior download.

    With a URL fetch the download owns the first ``_DOWNLOAD_BAR_SHARE`` of the
    bar, so the pipeline's [0, 1] is compressed into the rest. File inputs use
    the full bar unchanged. ``None`` (unknown progress) passes through.
    """
    if frac is None:
        return None
    if not fetched:
        return frac
    return _DOWNLOAD_BAR_SHARE + (1.0 - _DOWNLOAD_BAR_SHARE) * frac


class Worker(QObject):
    """Owns one fetch(+)``pipeline.run`` invocation; lives on a background thread.

    Signals:
        progress(stage, fraction, msg) — fraction is ``float | None`` (``object``
            so ``None`` survives the signal), forwarded from the download and the
            pipeline's ProgressCallback.
        finished(rc) — pipeline returned ``rc`` (0 == success).
        failed(message) — an exception was raised; ``message`` is user-facing.
        resolved(output_dir) — for URL inputs, the per-song output folder once the
            download has determined it (so the window can offer "open folder").
    """

    progress = Signal(str, object, str)
    finished = Signal(int)
    failed = Signal(str)
    resolved = Signal(str)

    def __init__(self, opts: pipeline.Options) -> None:
        super().__init__()
        self._opts = opts

    @Slot()
    def run(self) -> None:
        fetched = self._opts.source_url is not None
        try:
            if fetched:
                self._fetch_source()
            # Wire the pipeline's callback to our cross-thread signal, scaling it
            # to sit after the download portion of the bar when we fetched a URL.
            self._opts.progress_callback = (
                lambda stage, frac, msg: self.progress.emit(
                    stage, _scale_pipeline_fraction(frac, fetched=fetched), msg
                )
            )
            rc = pipeline.run(self._opts)
        except BandPrepareError as exc:
            self.failed.emit(exc.message)
        except Exception as exc:  # noqa: BLE001 - surface anything to the user
            self.failed.emit(str(exc))
        else:
            self.finished.emit(rc)

    def _fetch_source(self) -> None:
        """Download the URL audio, mapping its progress onto the bar's first slice."""

        def dl_cb(frac: float) -> None:
            frac = max(0.0, min(frac, 1.0))
            self.progress.emit("download", _DOWNLOAD_BAR_SHARE * frac, "")

        self.progress.emit("download", 0.0, "URL 음원 다운로드 / fetching audio")
        res = youtube.fetch(
            self._opts.source_url,
            # Windowed GUI has no meaningful cwd → default to the home folder.
            dest_base=portable_base(Path.home()),
            explicit_output=self._opts.output_dir,
            progress_cb=dl_cb,
            verbose=self._opts.verbose,
        )
        self._opts.input_path = res.audio_path
        self._opts.output_dir = res.output_dir
        self.resolved.emit(str(res.output_dir))
        self.progress.emit(
            "download", _DOWNLOAD_BAR_SHARE, f"다운로드 완료 / downloaded: {res.title}"
        )
