"""Background separation worker.

Runs ``pipeline.run`` on a ``QThread`` so the UI stays responsive. The worker
NEVER touches widgets; it only emits signals, which Qt marshals back to the GUI
thread via queued connections. The pipeline's progress callback fires on this
worker thread, so it too is forwarded purely through a signal.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from .. import pipeline
from ..errors import BandPrepareError


class Worker(QObject):
    """Owns one ``pipeline.run`` invocation; lives on a background thread.

    Signals:
        progress(stage, fraction, msg) — fraction is ``float | None`` (``object``
            so ``None`` survives the signal), forwarded straight from the
            pipeline's ProgressCallback.
        finished(rc) — pipeline returned ``rc`` (0 == success).
        failed(message) — an exception was raised; ``message`` is user-facing.
    """

    progress = Signal(str, object, str)
    finished = Signal(int)
    failed = Signal(str)

    def __init__(self, opts: pipeline.Options) -> None:
        super().__init__()
        self._opts = opts

    @Slot()
    def run(self) -> None:
        # Wire the pipeline's callback to our cross-thread signal.
        self._opts.progress_callback = (
            lambda stage, frac, msg: self.progress.emit(stage, frac, msg)
        )
        try:
            rc = pipeline.run(self._opts)
        except BandPrepareError as exc:
            self.failed.emit(exc.message)
        except Exception as exc:  # noqa: BLE001 - surface anything to the user
            self.failed.emit(str(exc))
        else:
            self.finished.emit(rc)
