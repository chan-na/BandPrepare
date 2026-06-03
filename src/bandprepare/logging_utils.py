"""Tiny logging helpers shared across the package.

We keep console output friendly (stage banners, step lines) and route everything
through the standard ``logging`` module so ``-v/--verbose`` can flip the level.
"""

from __future__ import annotations

import logging
import sys

LOGGER_NAME = "bandprepare"


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def setup_logging(verbose: bool) -> logging.Logger:
    logger = get_logger()
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    return logger


def stage(logger: logging.Logger, number: int, total: int, title: str) -> None:
    """Print a prominent stage banner, e.g. ``[1/2] 악기 분리 ...``."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("[%d/%d] %s", number, total, title)
    logger.info("=" * 60)


def step(logger: logging.Logger, message: str) -> None:
    logger.info("  - %s", message)
