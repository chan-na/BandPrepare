"""Stop a frozen bundle from spawning a do-nothing duplicate of itself.

`tqdm` (the progress bars in demucs / LarsNet and the weight downloads) builds a
**multiprocessing** ``RLock`` the first time any bar is shown
(``TqdmDefaultWriteLock`` → ``multiprocessing.RLock()``). Creating that lock
registers a semaphore, which starts the multiprocessing ``resource_tracker``
process — and on macOS/Windows (start method ``spawn``) that, plus any pool
worker, **re-executes the frozen binary**. The bundled entry point isn't a real
Python interpreter, so the child re-runs ``main()`` instead of acting as a
worker: a second, idle GUI window appears (or the CLI trips on argparse:
``unrecognized arguments: -B -S -I -c``).

We never use multiprocess tqdm, so hand tqdm a plain threading lock before any
bar is created: no semaphore, no resource_tracker, no duplicate process.
``multiprocessing.freeze_support()`` is the documented companion (a no-op except
in a frozen Windows child, where it diverts the child to worker mode).

Frozen-only; dev/test keep stock behaviour.
"""

from __future__ import annotations

import sys


def configure_multiprocessing() -> None:
    """Prevent the frozen app from spawning a duplicate process. Frozen-only."""
    if not getattr(sys, "frozen", False):
        return
    import multiprocessing

    multiprocessing.freeze_support()
    try:
        import threading

        from tqdm import tqdm

        # Replaces TqdmDefaultWriteLock (which holds a multiprocessing RLock) so
        # tqdm.get_lock() never constructs the mp lock that spawns the tracker.
        tqdm.set_lock(threading.RLock())
    except Exception:  # noqa: BLE001 - tqdm is best-effort; never block startup
        pass
