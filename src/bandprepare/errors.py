"""Error types and process exit codes.

Messages are intentionally bilingual (Korean / English) so the tool is usable
for the target audience (band members) while still being clear in logs.
"""

from __future__ import annotations


# Exit codes. 0 is success; 130 is reserved for KeyboardInterrupt (handled in cli).
EXIT_OK = 0
EXIT_USAGE = 2          # bad CLI usage / arguments
EXIT_INPUT = 3          # input file missing / unreadable / not audio
EXIT_DEPENDENCY = 4     # a required external dependency (e.g. ffmpeg) is missing
EXIT_MODEL = 5          # model weights could not be downloaded / loaded
EXIT_SEPARATION = 6     # separation itself failed
EXIT_INTERRUPTED = 130  # Ctrl-C


class BandPrepareError(Exception):
    """Base class for expected, user-facing errors.

    Carries an ``exit_code`` so ``cli.main`` can turn it into a clean process
    exit instead of a traceback.
    """

    exit_code = EXIT_SEPARATION

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InputError(BandPrepareError):
    """The input audio file is missing, unreadable, or not decodable."""

    exit_code = EXIT_INPUT


class DependencyError(BandPrepareError):
    """A required external tool (ffmpeg) or library is unavailable."""

    exit_code = EXIT_DEPENDENCY


class ModelError(BandPrepareError):
    """Model weights could not be downloaded or loaded."""

    exit_code = EXIT_MODEL


class SeparationError(BandPrepareError):
    """The separation step failed at runtime."""

    exit_code = EXIT_SEPARATION
