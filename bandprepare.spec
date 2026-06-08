# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for BandPrepare — one-folder bundle (GUI + CLI).

Build:   .venv/bin/python -m PyInstaller bandprepare.spec
Output:  dist/bandprepare/   — two binaries over one shared set of libraries:
           bandprepare        (GUI, primary;  run dist/bandprepare/bandprepare)
           bandprepare-cli     (CLI;  run dist/bandprepare/bandprepare-cli <song>)

Design notes (see PORTABLE-GUI-ROADMAP.md):
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
- BS-RoFormer IS bundled (Phase 5a): it only needs rotary-embedding-torch /
  einops / beartype — no numba. Mel-Band RoFormer is still EXCLUDED (D6) because
  its vendored model eagerly imports librosa (``from librosa import filters``),
  which drags in the numba/llvmlite JIT stack that is awkward to freeze. Mel-Band
  is enabled separately in Phase 5b by vendoring librosa.filters.mel (pure numpy)
  to drop librosa/numba/llvmlite. Selecting Mel-Band in this bundle therefore
  still errors at run time; BS-RoFormer and the other models work.
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
    # vendored RoFormer *models* are imported lazily inside build_model().
    "bandprepare.separation.roformer",
    # BS-RoFormer model + its deps (Phase 5a). build_model() imports these lazily,
    # so name them explicitly. einops.layers.torch and packaging are pulled in by
    # the vendored model/attend but are easy for PyInstaller to miss. Mel-Band
    # (vendor.roformer.mel_band_roformer) + librosa stay in ``excludes`` (5b).
    "bandprepare.vendor.roformer",
    "bandprepare.vendor.roformer.bs_roformer",
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
        # Mel-Band RoFormer only (D6 / Phase 5b). BS-RoFormer is now bundled (its
        # modules + rotary-embedding-torch/beartype/einops moved to hiddenimports).
        # mel_band_roformer eagerly imports librosa, which drags in numba/llvmlite;
        # keep all four out until 5b vendors librosa.filters.mel. The backend module
        # bandprepare.separation.roformer is NOT excluded (MDX23C reuses its _demix),
        # and its build_model() mel branch imports mel_band_roformer lazily, so
        # excluding the model alone is enough to keep librosa out of the graph.
        "bandprepare.vendor.roformer.mel_band_roformer",
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

# Settings shared by both EXE targets (differ only in pyz/scripts/name).
exe_kwargs = dict(
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

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="bandprepare", **exe_kwargs)
exe_cli = EXE(
    pyz_cli, a_cli.scripts, [], exclude_binaries=True, name="bandprepare-cli", **exe_kwargs
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
