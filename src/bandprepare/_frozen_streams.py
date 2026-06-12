"""Give a windowed (no-console) frozen app usable std streams.

On Windows, PyInstaller builds with ``console=False`` start like ``pythonw.exe``:
``sys.stdout`` and ``sys.stderr`` are ``None``. Anything that writes to them —
tqdm progress bars inside demucs/LarsNet, ``logging.StreamHandler``, stray
``print`` — then dies with ``AttributeError: 'NoneType' object has no attribute
'write'``, which the GUI surfaces as a separation failure.

macOS never hits this (Finder-launched .apps get real streams routed to the
unified log), which is why the bug only shows on Windows. The fix is the
standard one: point any ``None`` stream at ``os.devnull``. Guarding on ``None``
(rather than ``sys.frozen``) keeps dev/test behaviour untouched while also
covering plain ``pythonw.exe`` runs.
"""

from __future__ import annotations

import os
import sys


def configure_std_streams() -> None:
    """Replace ``None`` std streams with devnull writers. No-op otherwise."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 - lives for the process
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 - lives for the process
