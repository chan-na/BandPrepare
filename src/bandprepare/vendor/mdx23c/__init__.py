"""Vendored MDX23C (TFC-TDF v3) source-separation model definition.

``tfc_tdf_v3.py`` is copied verbatim from
ZFTurbo/Music-Source-Separation-Training at tag ``v1.0.12`` — the only change is
the cross-file ``utils`` import, made relative to the bundled :mod:`._utils`.
It is pinned to that tag so the architecture stays consistent with the
pretrained drum checkpoint we download (whose ``state_dict`` keys must match).

KUIELab TFC-TDF v3 architecture (MIT). Unlike the RoFormer models, this one
needs only the base ``torch`` stack — no optional ``[roformer]`` extras.
"""

from __future__ import annotations

from .tfc_tdf_v3 import TFC_TDF_net

__all__ = ["TFC_TDF_net"]
