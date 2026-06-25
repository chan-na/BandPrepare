"""Shared abstractions for selectable separation models.

A ``Separator`` turns one ``(channels, samples)`` waveform into a dict of named
sub-tracks (instrument stems, or drum-kit pieces). Each concrete backend
(Demucs, LarsNet, RoFormer, ...) lives in its own module and is described to the
rest of the app by a :class:`ModelInfo` registered in ``registry.py``.

Keeping ``torch`` out of this module's runtime imports lets ``--list-models``
stay cheap; the tensor types are referenced only for type-checking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only
    import torch

# Model-internal progress reporter: called with a fraction in [0, 1] as a
# backend works through its chunks / sub-models. Backends may call it at any
# granularity (or never, if they cannot report); fractions are estimates, so
# callers should clamp and tolerate values that stop short of 1.0.
ProgressFn = Callable[[float], None]


@dataclass(frozen=True)
class ModelInfo:
    """Static description of a selectable model.

    ``output_stems`` is the authoritative set/order of tracks the model emits;
    the CLI validates ``--stems`` against it and the pipeline uses it for
    re-run skip logic. ``samplerate``/``channels`` describe the audio the model
    consumes and produces, so the pipeline can load input without first
    constructing the (heavy) model.
    """

    id: str                          # CLI value, e.g. "htdemucs_ft"
    kind: str                        # "stem" | "drum"
    display: str                     # log label, e.g. "Demucs htdemucs_ft"
    output_stems: tuple[str, ...]
    samplerate: int
    load: "Loader"                   # (info, device, **opts) -> Separator
    channels: int = 2
    license_note: str = ""           # e.g. "CC BY-NC 4.0 (비상업용 / non-commercial)"
    description: str = ""            # one-line bilingual help, shown as a GUI tooltip


@runtime_checkable
class Separator(Protocol):
    """A loaded model ready to separate one waveform."""

    info: ModelInfo

    def separate(
        self, wav: "torch.Tensor", input_sr: int, *, progress: bool = True,
        progress_cb: ProgressFn | None = None,
    ) -> dict[str, "torch.Tensor"]:
        """Return ``{stem_name: (channels, samples)}`` at ``self.info.samplerate``."""
        ...


# A loader builds a ready-to-use Separator for a given device. Model-specific
# knobs (shifts, wiener_exponent, ...) are passed as keyword arguments and
# ignored by backends that don't use them.
Loader = Callable[..., Separator]
