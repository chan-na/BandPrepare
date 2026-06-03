"""BandPrepare — split a song into per-instrument practice tracks.

Stage 1 separates a mixed recording into instrument stems with Demucs
(``htdemucs_6s``). Stage 2 further splits the drum stem into individual
drum-kit pieces with LarsNet.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
