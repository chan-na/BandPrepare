"""Minimal helper vendored from ZFTurbo's ``utils.py`` (v1.0.12).

``tfc_tdf_v3.py`` imports a single function from the upstream ``utils`` module;
the rest of that module pulls in heavy/unrelated dependencies, so we vendor just
this helper and make the import relative.
"""

from __future__ import annotations


def prefer_target_instrument(config):
    """Return the list of instruments the model predicts.

    If a single ``target_instrument`` is set, predict only that; otherwise
    predict every entry in ``instruments``. Mirrors ZFTurbo's
    ``utils.prefer_target_instrument``.
    """
    if getattr(config.training, "target_instrument", None) is not None:
        return [config.training.target_instrument]
    return config.training.instruments
