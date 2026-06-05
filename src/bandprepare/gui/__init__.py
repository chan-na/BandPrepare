"""Desktop GUI (PySide6) — a thin layer over the separation pipeline.

The GUI collects options from widgets, hands them to ``pipeline.run`` on a
background ``QThread``, and reflects the pipeline's progress callback in a
progress bar + log panel. It adds no audio logic of its own.
"""

from __future__ import annotations

from .app import main

__all__ = ["main"]
