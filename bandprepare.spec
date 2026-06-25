# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for BandPrepare — one-folder bundle (GUI + CLI).

Build:   .venv/bin/python -m PyInstaller bandprepare.spec
Output:  dist/bandprepare/   — two binaries over one shared set of libraries:
           bandprepare        (GUI, primary;  run dist/bandprepare/bandprepare)
           bandprepare-cli     (CLI;  run dist/bandprepare/bandprepare-cli <song>)

Design notes (see ARCHITECTURE.md §12):
- One-folder (onedir): torch and the interpreter are native code, so a single
  cross-platform binary is impossible — build per platform (D1/D7). one-file is
  avoided because it re-extracts ~GBs to a temp dir on every launch (worse for a
  CLI, which is invoked repeatedly).
- Two EXE targets share ONE COLLECT: the CLI is a second entry point built over
  the same collected libraries (a.binaries/a.datas), so it adds only a small
  binary (its own PYZ + bootstrap), not another ~GB of torch.
- Model weights are NOT bundled (D5): they download on first run into a cache
  OUTSIDE the bundle (BANDPREPARE_CACHE → XDG_CACHE_HOME → ~/.cache), which is
  writable from a frozen app.
- ffmpeg ships via imageio-ffmpeg (collected below) — no system ffmpeg needed.
  Note: imageio-ffmpeg has no ffprobe and its binary is version-named; the
  decode path in audio.py accounts for that.
- BS-RoFormer and Mel-Band RoFormer are BOTH bundled (Phases 5a/5b): they need
  only rotary-embedding-torch / einops / beartype. Mel-Band's lone librosa use
  (``filters.mel``) is vendored as pure NumPy (vendor/roformer/_mel.py), so the
  numba/llvmlite JIT stack that D6 flagged as awkward-to-freeze is gone entirely
  — librosa/numba/llvmlite are no longer in the dependency graph at all.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

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

# CUDA runtime libs (the linux-cuda / windows-cuda bundles). torch's CUDA (cu*)
# wheels ship the GPU runtime as SEPARATE top-level `nvidia-*-cu12` packages
# (libcublas/libcudnn/libcudart/... under site-packages/nvidia/<lib>/lib), which
# collect_all("torch") above does NOT pull in — so a Linux CUDA bundle would be
# missing them and fail at runtime. Collect every installed `nvidia.*` subpackage
# when present. CPU-only builds have no `nvidia` package, so the import fails and
# this is skipped: ONE spec serves all six bundles (cpu-only + cuda × linux/win,
# mac). On Windows the CUDA DLLs live inside torch/lib and are already collected,
# so `nvidia` is typically absent there too — this loop is a no-op then.
try:
    import importlib
    import pkgutil

    nvidia = importlib.import_module("nvidia")
    for _mod in pkgutil.iter_modules(nvidia.__path__, "nvidia."):
        n_datas, n_binaries, n_hidden = collect_all(_mod.name)
        datas += n_datas
        binaries += n_binaries
        hiddenimports += n_hidden
except ImportError:
    pass  # CPU-only build — no CUDA runtime to bundle.

# yt-dlp (URL/YouTube audio input) dynamically imports its many site extractors,
# so collect every submodule explicitly or PyInstaller misses them at runtime.
# collect_data_files picks up its bundled data; it has no native binaries.
hiddenimports += collect_submodules("yt_dlp")
datas += collect_data_files("yt_dlp")

# Our backends are imported lazily inside registry loader closures, so name them
# explicitly. RoFormer modules are deliberately omitted (see header / D6) and are
# listed under ``excludes`` below.
hiddenimports += [
    "bandprepare.pipeline",
    "bandprepare.cli",
    "bandprepare.audio",
    "bandprepare.click",
    "bandprepare.youtube",
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
    # vendored RoFormer *models* are imported lazily inside build_model().
    "bandprepare.separation.roformer",
    # RoFormer models + their deps (Phases 5a/5b). build_model() imports these
    # lazily, so name them explicitly. einops.layers.torch and packaging are
    # pulled in by the vendored model/attend but are easy for PyInstaller to miss.
    # Mel-Band uses vendor/roformer/_mel.py (pure NumPy) instead of librosa, so no
    # numba/llvmlite/librosa enter the graph.
    "bandprepare.vendor.roformer",
    "bandprepare.vendor.roformer.bs_roformer",
    "bandprepare.vendor.roformer.mel_band_roformer",
    "bandprepare.vendor.roformer.attend",
    "rotary_embedding_torch",
    "beartype",
    "einops",
    "einops.layers.torch",
    "packaging",
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

# Window/taskbar icon, resolved at runtime as Path(gui/__file__)/icon.png — same
# next-to-the-module pattern as the YAML configs above. Regenerate from
# assets/icon.svg with packaging/make_icons.py.
datas.append((str(src_root / "bandprepare" / "gui" / "icon.png"), "bandprepare/gui"))

# Both entry points (GUI + CLI) analyse the same dependency graph; only the
# top-level script differs. Share one kwargs dict so they never drift.
analysis_kwargs = dict(
    pathex=[str(src_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # librosa/numba/llvmlite are no longer imported: Mel-Band RoFormer's only
        # librosa call (filters.mel) is vendored as pure NumPy in
        # vendor/roformer/_mel.py (Phase 5b / D6). Keep them excluded as a belt-
        # and-braces guard so a stray transitive import can never re-introduce the
        # heavy JIT stack into the bundle.
        "numba",
        "llvmlite",
        "librosa",
        # Dev/test-only weight.
        "pytest",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

# GUI entry (primary) — provides the shared a.binaries/a.datas used by COLLECT.
a = Analysis([str(project_root / "packaging" / "bandprepare_gui.py")], **analysis_kwargs)
# CLI entry — same graph, different script. Its binaries/datas are intentionally
# NOT passed to COLLECT (a.binaries is the shared superset); only its PYZ + the
# bootstrap script become the small `bandprepare-cli` binary in the same folder.
a_cli = Analysis([str(project_root / "packaging" / "bandprepare_cli.py")], **analysis_kwargs)

pyz = PYZ(a.pure)
pyz_cli = PYZ(a_cli.pure)

# Settings shared by both EXE targets (differ only in pyz/scripts/name/console).
# console is set PER-EXE below: the GUI is windowed (console=False) so the macOS
# .app launches straight to a window instead of spawning Terminal.app, while the
# CLI keeps its console. Note: console=False only changes the .app's plist/launch
# behaviour — running the raw binary from a terminal (as the SELFTEST does) still
# writes to stdout/stderr normally.
exe_kwargs = dict(
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # host arch; universal2 is impractical with torch (D7/R4).
    codesign_identity=None,
    entitlements_file=None,
)
if sys.platform == "win32":
    # Embedded .exe icon (Windows-only concept; macOS uses the BUNDLE .icns and
    # Linux the runtime window icon). Regenerated by packaging/make_icons.py.
    exe_kwargs["icon"] = str(project_root / "assets" / "icon.ico")

# GUI: windowed (no console) → double-clicking BandPrepare.app opens the window
# directly. CLI: keep the console; it is a terminal program.
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="bandprepare", console=False, **exe_kwargs
)
exe_cli = EXE(
    pyz_cli, a_cli.scripts, [], exclude_binaries=True, name="bandprepare-cli", console=True,
    **exe_kwargs,
)

# One COLLECT, both EXEs, one shared set of libraries → dist/bandprepare/ holding
# `bandprepare` and `bandprepare-cli` side by side over the same _internal libs.
coll = COLLECT(
    exe,
    exe_cli,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="bandprepare",
)

# macOS: wrap the onedir COLLECT in a windowed .app so Finder/LaunchServices
# launches the GUI directly (no Terminal). The .app's primary executable is the
# first EXE in COLLECT (the GUI); `bandprepare-cli` rides along inside
# Contents/MacOS and stays usable from a terminal. Distribution still needs
# codesign + notarize (Phase 5) or Gatekeeper will warn on first open.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="BandPrepare.app",
        icon=str(project_root / "assets" / "icon.icns"),
        bundle_identifier="com.bandprepare.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSBackgroundOnly": False,
            "CFBundleShortVersionString": "0.3.0",
        },
    )
