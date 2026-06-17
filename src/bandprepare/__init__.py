"""BandPrepare — split a song into per-instrument practice tracks.

Stage 1 separates a mixed recording into instrument stems with Demucs
(``htdemucs_ft`` by default). Stage 2 further splits the drum stem into
individual drum-kit pieces (MDX23C DrumSep by default).
"""

__version__ = "0.3.0"

__all__ = ["__version__"]
