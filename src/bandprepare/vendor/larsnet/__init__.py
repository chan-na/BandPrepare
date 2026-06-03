"""Vendored copy of LarsNet (polimi-ispl/larsnet).

See ``larsnet.py`` header for attribution and license. Only the cross-file
import was changed to be relative so it works inside the ``bandprepare``
package.
"""

from .larsnet import LarsNet
from .unet import UNet, UNetWaveform, UNetUtils

__all__ = ["LarsNet", "UNet", "UNetWaveform", "UNetUtils"]
