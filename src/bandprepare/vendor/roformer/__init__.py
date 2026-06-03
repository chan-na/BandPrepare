"""Vendored RoFormer source-separation model definitions.

``bs_roformer.py``, ``mel_band_roformer.py`` and ``attend.py`` are copied
verbatim (only the cross-file ``attend`` import was made relative) from
ZFTurbo/Music-Source-Separation-Training at tag ``v1.0.12`` — itself derived
from lucidrains' implementations of BS-RoFormer / Mel-Band RoFormer (MIT).

They are pinned to that tag so the architecture stays consistent with the
pretrained checkpoints we download (whose ``state_dict`` keys must match).

``MelBandRoformer`` additionally requires ``librosa`` at import time, so it is
imported lazily by the backend rather than re-exported here.
"""

from __future__ import annotations

from .bs_roformer import BSRoformer

__all__ = ["BSRoformer"]
