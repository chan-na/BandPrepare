# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for BandPrepare — one-folder GUI bundle.

Build:   .venv/bin/python -m PyInstaller bandprepare.spec
Output:  dist/bandprepare/           (run dist/bandprepare/bandprepare)

Design notes (see PORTABLE-GUI-ROADMAP.md):
- One-folder (onedir): torch and the interpreter are native code, so a single
  cross-platform binary is impossible — build per platform (D1/D7). one-file is
  avoided because it re-extracts ~GBs to a temp dir on every launch.
- Model weights are NOT bundled (D5): they download on first run into a cache
  OUTSIDE the bundle (BANDPREPARE_CACHE → XDG_CACHE_HOME → ~/.cache), which is
  writable from a frozen app.
- ffmpeg ships via imageio-ffmpeg (collected below) — no system ffmpeg needed.
  Note: imageio-ffmpeg has no ffprobe and its binary is version-named; the
  decode path in audio.py accounts for that.
- RoFormer is intentionally EXCLUDED from this initial bundle (D6): its
  numba/llvmlite JIT stack is awkward to freeze, and vendor/roformer eagerly
  imports rotary-embedding-torch/einops/beartype. The bundled stem/drum models
  (Demucs, LarsNet, DrumSep, MDX23C) need only the base torch stack. Selecting a
  RoFormer model in this bundle therefore errors at run time (added in Phase 5).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH)
src_root = project_root / "src"

datas = []
binaries = []
hiddenimports = []

# Heavy third-party packages: pull in their data files, dynamic libs, and
# submodules wholesale (R1: torch/PySide6 plugins are easy to miss otherwise).
for pkg in ("torch", "torchaudio", "demucs", "soundfile", "imageio_ffmpeg", "PySide6"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# Our backends are imported lazily inside registry loader closures, so name them
# explicitly. RoFormer modules are deliberately omitted (see header / D6) and are
# listed under ``excludes`` below.
hiddenimports += [
    "bandprepare.pipeline",
    "bandprepare.cli",
    "bandprepare.audio",
    "bandprepare.device",
    "bandprepare.errors",
    "bandprepare.logging_utils",
    "bandprepare.gui.app",
    "bandprepare.gui.worker",
    "bandprepare.separation.registry",
    "bandprepare.separation.base",
    "bandprepare.separation.stems",
    "bandprepare.separation.drums",
    "bandprepare.separation.drumsep",
    "bandprepare.separation.mdx23c",
    # The MDX23C backend reuses roformer._demix (the shared chunked-overlap
    # inference engine), and roformer.py is light at module level — the heavy
    # vendored RoFormer *models* are imported lazily inside build_model(). So the
    # backend module is bundled; only vendor.roformer.* + its deps are excluded.
    "bandprepare.separation.roformer",
    "bandprepare.separation.download",
    "bandprepare.vendor.larsnet",
    "bandprepare.vendor.larsnet.larsnet",
    "bandprepare.vendor.larsnet.unet",
    "bandprepare.vendor.mdx23c",
    "bandprepare.vendor.mdx23c.tfc_tdf_v3",
    "bandprepare.vendor.mdx23c._utils",
    # demucs runtime deps that are imported lazily / indirectly.
    "julius",
    "lameenc",
    "dora",
    "yaml",
]

# Vendored YAML configs must land next to the package tree so the runtime lookup
# Path(__file__).parent.parent / "vendor" / <model> / "configs" resolves inside
# the bundle (audio/mdx23c/roformer read them with plain open()).
for yaml_path in (src_root / "bandprepare" / "vendor").rglob("*.yaml"):
    dest_dir = yaml_path.parent.relative_to(src_root)  # e.g. bandprepare/vendor/mdx23c/configs
    datas.append((str(yaml_path), str(dest_dir)))

a = Analysis(
    [str(project_root / "packaging" / "bandprepare_gui.py")],
    pathex=[str(src_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # RoFormer stack (D6) — kept out of the initial bundle. Note: the backend
        # module bandprepare.separation.roformer is NOT excluded (MDX23C reuses
        # its _demix); only the vendored models and their JIT-heavy deps are.
        "bandprepare.vendor.roformer",
        "bandprepare.vendor.roformer.bs_roformer",
        "bandprepare.vendor.roformer.mel_band_roformer",
        "bandprepare.vendor.roformer.attend",
        "numba",
        "llvmlite",
        "rotary_embedding_torch",
        "beartype",
        "einops",
        "librosa",
        # Dev/test-only weight.
        "pytest",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bandprepare",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # PoC keeps a console so logs / the BANDPREPARE_GUI_SELFTEST output are
    # visible. Phase 5 switches to a windowed macOS .app (+ codesign/notarize).
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # host arch; universal2 is impractical with torch (D7/R4).
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="bandprepare",
)
