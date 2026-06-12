#!/usr/bin/env python
"""Render assets/icon.svg into every icon format the build consumes.

Outputs:
  assets/icon.icns              macOS bundle icon (BUNDLE in bandprepare.spec; built on macOS only)
  assets/icon.ico               Windows exe icon (EXE in bandprepare.spec)
  src/bandprepare/gui/icon.png  runtime window/taskbar icon (set in gui/app.py, ships in the wheel/bundle)

assets/icon.svg is the single source of truth — rerun this after editing it:

  QT_QPA_PLATFORM=offscreen .venv/bin/python packaging/make_icons.py

Needs PySide6 (the ``gui`` extra) for SVG rendering; no other dependencies.
The .ico is written by hand (PNG-compressed entries) so Pillow isn't needed.
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

REPO = Path(__file__).resolve().parent.parent
SVG = REPO / "assets" / "icon.svg"
ICNS = REPO / "assets" / "icon.icns"
ICO = REPO / "assets" / "icon.ico"
GUI_PNG = REPO / "src" / "bandprepare" / "gui" / "icon.png"

# (point size, scale) pairs Apple's iconutil expects in an .iconset.
ICONSET_SIZES = [(16, 1), (16, 2), (32, 1), (32, 2), (128, 1), (128, 2),
                 (256, 1), (256, 2), (512, 1), (512, 2)]
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
GUI_PNG_SIZE = 256


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return bytes(buf.data())


def write_ico(path: Path, pngs: list[tuple[int, bytes]]) -> None:
    """Minimal .ico writer: PNG-compressed entries (supported since Vista)."""
    header = struct.pack("<HHH", 0, 1, len(pngs))
    entries = b""
    offset = 6 + 16 * len(pngs)
    blobs = b""
    for size, png in pngs:
        entries += struct.pack(
            "<BBBBHHII",
            size % 256, size % 256,  # 0 encodes 256
            0, 0, 1, 32, len(png), offset,
        )
        offset += len(png)
        blobs += png
    path.write_bytes(header + entries + blobs)


def write_icns(renderer: QSvgRenderer) -> bool:
    """Build .icns via Apple's iconutil; skipped off-macOS (icns is mac-only)."""
    if sys.platform != "darwin":
        return False
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for points, scale in ICONSET_SIZES:
            suffix = f"@{scale}x" if scale > 1 else ""
            name = f"icon_{points}x{points}{suffix}.png"
            (iconset / name).write_bytes(render_png(renderer, points * scale))
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS)], check=True
        )
    return True


def main() -> int:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        print(f"error: cannot render {SVG}", file=sys.stderr)
        return 1

    GUI_PNG.write_bytes(render_png(renderer, GUI_PNG_SIZE))
    print(f"wrote {GUI_PNG}")

    write_ico(ICO, [(s, render_png(renderer, s)) for s in ICO_SIZES])
    print(f"wrote {ICO}")

    if write_icns(renderer):
        print(f"wrote {ICNS}")
    else:
        print(f"skipped {ICNS} (iconutil needs macOS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
