"""Main window, Options builder, and ``main()`` entry point.

UI strings are bilingual (Korean / English) to match the rest of the project.
The window only gathers state and displays progress; all audio work happens in
:mod:`bandprepare.gui.worker` on a background thread.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import audio
from .._frozen_mp import configure_multiprocessing
from .._ssl_certs import configure_ssl_cert_file
from ..cli import default_output_dir
from ..device import VALID_CHOICES
from ..pipeline import Options
from ..separation import registry
from .worker import Worker

# Audio extensions accepted via drag-and-drop / file dialog. Decoding ultimately
# relies on ffmpeg for compressed formats; SUPPORTED_FORMATS covers outputs.
_AUDIO_EXTS = (".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".aiff", ".aif")


def build_options(
    *,
    input_path: Path,
    output_dir: Path,
    stem_model: str,
    drum_model: str,
    stems: list[str],
    minus: list[str],
    fmt: str,
    device_choice: str,
    drum_split: bool,
    keep_drums_stem: bool,
    overwrite: bool,
    verbose: bool,
) -> Options:
    """Build an :class:`Options` from plain UI state (no widgets involved).

    Kept pure so it can be unit-tested without a display. The window calls this
    with values read from its widgets.
    """
    return Options(
        input_path=Path(input_path),
        output_dir=Path(output_dir),
        stems=list(stems),
        fmt=fmt,
        device_choice=device_choice,
        stem_model=stem_model,
        drum_model=drum_model,
        drum_split=drum_split,
        keep_drums_stem=keep_drums_stem,
        overwrite=overwrite,
        verbose=verbose,
        minus=list(minus),
    )


class MainWindow(QMainWindow):
    """Top-level window: pick a file + options, run, watch progress."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BandPrepare — 악기 분리 / Instrument separation")
        self.setAcceptDrops(True)

        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self._last_output_dir: Path | None = None
        self._stem_checks: dict[str, QCheckBox] = {}
        self._minus_checks: dict[str, QCheckBox] = {}

        self._build_ui()
        self._populate_models()
        self._rebuild_stem_widgets()
        self._update_drum_controls_enabled()

    # ---- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        # Input file: drag-and-drop label + chooser button.
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText(
            "오디오 파일을 여기로 끌어다 놓거나 선택하세요 / "
            "Drag an audio file here or choose one"
        )
        self._input_edit.setReadOnly(True)
        choose_file = QPushButton("파일 선택 / Choose file…")
        choose_file.clicked.connect(self._choose_file)
        in_row = QHBoxLayout()
        in_row.addWidget(self._input_edit, 1)
        in_row.addWidget(choose_file)
        root.addWidget(QLabel("입력 파일 / Input file"))
        root.addLayout(in_row)

        # Models + format + device.
        form = QFormLayout()
        self._stem_combo = QComboBox()
        self._stem_combo.currentIndexChanged.connect(self._on_stem_model_changed)
        form.addRow("악기 모델 / Stem model", self._stem_combo)

        self._drum_combo = QComboBox()
        form.addRow("드럼 모델 / Drum model", self._drum_combo)

        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(list(audio.SUPPORTED_FORMATS))
        form.addRow("포맷 / Format", self._fmt_combo)

        self._device_combo = QComboBox()
        self._device_combo.addItems(list(VALID_CHOICES))
        form.addRow("장치 / Device", self._device_combo)
        root.addLayout(form)

        # Stem selection (which stems to keep).
        self._stems_group = QGroupBox("저장할 스템 / Stems to keep")
        self._stems_layout = QHBoxLayout(self._stems_group)
        root.addWidget(self._stems_group)

        # Mix-minus selection.
        self._minus_group = QGroupBox(
            "마이너스원 (빼낼 스템) / Mix-minus (stems to remove)"
        )
        self._minus_layout = QHBoxLayout(self._minus_group)
        root.addWidget(self._minus_group)

        # Boolean flags.
        flags_row = QHBoxLayout()
        self._drum_split_check = QCheckBox("드럼 분리 / Drum split")
        self._drum_split_check.setChecked(True)
        self._drum_split_check.toggled.connect(self._update_drum_controls_enabled)
        self._keep_drums_check = QCheckBox("드럼 스템 유지 / Keep drums stem")
        self._overwrite_check = QCheckBox("덮어쓰기 / Overwrite")
        self._verbose_check = QCheckBox("자세히 / Verbose")
        for cb in (
            self._drum_split_check,
            self._keep_drums_check,
            self._overwrite_check,
            self._verbose_check,
        ):
            flags_row.addWidget(cb)
        flags_row.addStretch(1)
        root.addLayout(flags_row)

        # Output folder.
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("출력 폴더 / Output folder")
        choose_folder = QPushButton("폴더 선택 / Choose folder…")
        choose_folder.clicked.connect(self._choose_folder)
        out_row = QHBoxLayout()
        out_row.addWidget(self._output_edit, 1)
        out_row.addWidget(choose_folder)
        root.addWidget(QLabel("출력 폴더 / Output folder"))
        root.addLayout(out_row)

        # Run + open-output buttons.
        action_row = QHBoxLayout()
        self._run_btn = QPushButton("분리 시작 / Run")
        self._run_btn.clicked.connect(self._on_run)
        self._open_btn = QPushButton("출력 폴더 열기 / Open output folder")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._open_output)
        action_row.addWidget(self._run_btn)
        action_row.addWidget(self._open_btn)
        root.addLayout(action_row)

        # Progress + log.
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        root.addWidget(self._progress)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        root.addWidget(self._log, 1)

        self.setCentralWidget(central)
        self.resize(680, 640)

    def _populate_models(self) -> None:
        for info in registry.STEM_MODELS.values():
            self._stem_combo.addItem(info.display, info.id)
        idx = self._stem_combo.findData(registry.DEFAULT_STEM_MODEL)
        if idx >= 0:
            self._stem_combo.setCurrentIndex(idx)

        for info in registry.DRUM_MODELS.values():
            self._drum_combo.addItem(info.display, info.id)
        idx = self._drum_combo.findData(registry.DEFAULT_DRUM_MODEL)
        if idx >= 0:
            self._drum_combo.setCurrentIndex(idx)

    # ---- dynamic stem / minus widgets --------------------------------------

    def _current_stem_id(self) -> str:
        data = self._stem_combo.currentData()
        return data if data is not None else registry.DEFAULT_STEM_MODEL

    def _rebuild_stem_widgets(self) -> None:
        """Regenerate stem + mix-minus checkboxes for the selected stem model."""
        stems = registry.resolve_stem(self._current_stem_id()).output_stems

        for layout, store in (
            (self._stems_layout, self._stem_checks),
            (self._minus_layout, self._minus_checks),
        ):
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            store.clear()

        for name in stems:
            keep = QCheckBox(name)
            keep.setChecked(True)  # keep all stems by default
            self._stems_layout.addWidget(keep)
            self._stem_checks[name] = keep

            minus = QCheckBox(name)
            minus.setChecked(False)  # remove nothing by default
            self._minus_layout.addWidget(minus)
            self._minus_checks[name] = minus

        self._stems_layout.addStretch(1)
        self._minus_layout.addStretch(1)

    def _on_stem_model_changed(self) -> None:
        self._rebuild_stem_widgets()
        self._update_drum_controls_enabled()

    def _model_has_drums(self) -> bool:
        return "drums" in registry.resolve_stem(self._current_stem_id()).output_stems

    def _update_drum_controls_enabled(self) -> None:
        """Drum-kit controls are only meaningful when the model emits 'drums'."""
        has_drums = self._model_has_drums()
        self._drum_combo.setEnabled(has_drums)
        self._drum_split_check.setEnabled(has_drums)
        # keep-drums-stem only matters while splitting an existing drums stem.
        self._keep_drums_check.setEnabled(has_drums and self._drum_split_check.isChecked())

    # ---- file / folder selection -------------------------------------------

    def _choose_file(self) -> None:
        pattern = " ".join(f"*{ext}" for ext in _AUDIO_EXTS)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "오디오 파일 선택 / Choose audio file",
            "",
            f"오디오 / Audio ({pattern});;모든 파일 / All files (*)",
        )
        if path:
            self._set_input(path)

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "출력 폴더 선택 / Choose output folder"
        )
        if path:
            self._output_edit.setText(path)

    def _set_input(self, path: str) -> None:
        self._input_edit.setText(path)
        # Pre-fill the output folder from the input filename.
        self._output_edit.setText(str(default_output_dir(path)))

    # ---- drag and drop ------------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        mime = event.mimeData()
        if mime.hasUrls() and any(
            Path(u.toLocalFile()).suffix.lower() in _AUDIO_EXTS
            for u in mime.urls()
            if u.isLocalFile()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if Path(path).suffix.lower() in _AUDIO_EXTS:
                self._set_input(path)
                event.acceptProposedAction()
                return
        event.ignore()

    # ---- run ----------------------------------------------------------------

    def _collect_options(self) -> Options | None:
        input_text = self._input_edit.text().strip()
        if not input_text:
            self._append_log(
                "입력 파일을 먼저 선택하세요. / Please choose an input file first."
            )
            return None
        output_text = self._output_edit.text().strip()
        if not output_text:
            output_text = str(default_output_dir(input_text))

        stems = [name for name, cb in self._stem_checks.items() if cb.isChecked()]
        if not stems:
            self._append_log(
                "최소 한 개의 스템을 선택하세요. / Select at least one stem."
            )
            return None
        minus = [name for name, cb in self._minus_checks.items() if cb.isChecked()]

        return build_options(
            input_path=Path(input_text),
            output_dir=Path(output_text),
            stem_model=self._current_stem_id(),
            drum_model=self._drum_combo.currentData() or registry.DEFAULT_DRUM_MODEL,
            stems=stems,
            minus=minus,
            fmt=self._fmt_combo.currentText(),
            device_choice=self._device_combo.currentText(),
            drum_split=self._drum_split_check.isChecked() and self._model_has_drums(),
            keep_drums_stem=self._keep_drums_check.isChecked(),
            overwrite=self._overwrite_check.isChecked(),
            verbose=self._verbose_check.isChecked(),
        )

    def _on_run(self) -> None:
        if self._thread is not None:
            return  # already running
        opts = self._collect_options()
        if opts is None:
            return

        self._last_output_dir = opts.output_dir
        self._run_btn.setEnabled(False)
        self._open_btn.setEnabled(False)
        self._progress.setValue(0)
        self._log.clear()

        self._thread = QThread(self)
        self._worker = Worker(opts)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    # ---- worker signal slots -----------------------------------------------

    def _on_progress(self, stage: str, fraction, msg: str) -> None:
        if fraction is not None:
            self._progress.setValue(int(fraction * 100))
        self._append_log(msg)

    def _on_finished(self, rc: int) -> None:
        if rc == 0:
            self._progress.setValue(100)
            self._append_log("완료 / done")
            self._open_btn.setEnabled(self._last_output_dir is not None)
        else:
            self._append_log(f"종료 코드 / exit code: {rc}")
        self._teardown_thread()

    def _on_failed(self, message: str) -> None:
        self._append_log(f"오류 / error: {message}")
        self._teardown_thread()

    def _teardown_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None
        self._run_btn.setEnabled(True)

    # ---- misc helpers -------------------------------------------------------

    def _append_log(self, msg: str) -> None:
        self._log.appendPlainText(msg)

    def _open_output(self) -> None:
        if self._last_output_dir is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._last_output_dir))
            )


def _selftest(app: QApplication, ffmpeg_path: str | None) -> int:
    """Headless packaging smoke test (no event loop, no model downloads).

    Used to verify a frozen (PyInstaller) bundle has every heavy dependency and
    vendored data file wired up — exercising the import + config-read paths that
    a real separation would hit, minus the network/weights. Triggered by
    ``BANDPREPARE_GUI_SELFTEST=1``.
    """
    import importlib

    app.processEvents()
    for mod in ("torch", "torchaudio", "demucs", "soundfile", "imageio_ffmpeg", "numpy", "yaml"):
        importlib.import_module(mod)
    # Bundled drum backend must import and find its vendored YAML config.
    from ..separation import registry
    from ..separation.mdx23c import _load_config

    registry.format_table()
    _load_config()

    # BS-RoFormer (Phase 5a) and Mel-Band RoFormer (Phase 5b) are both bundled:
    # the vendored models must import and build_model() must instantiate them
    # WITHOUT falling into the missing-deps degrade path (ModelError).
    # Instantiation only — no weights, no network. Mel-Band additionally exercises
    # the vendored pure-NumPy mel filter bank (vendor/roformer/_mel.py), proving
    # librosa/numba/llvmlite are not needed.
    from ..vendor.roformer.bs_roformer import BSRoformer  # noqa: F401
    from ..vendor.roformer.mel_band_roformer import MelBandRoformer  # noqa: F401
    from ..separation.roformer import _load_config as _load_roformer_config
    from ..separation.roformer import build_model as _build_roformer

    _build_roformer("bs_roformer", _load_roformer_config("bs_roformer_4stem.yaml"))
    _build_roformer("mel_band_roformer", _load_roformer_config("mel_band_vocals_kj.yaml"))

    # SSL_CERT_FILE is set by configure_ssl_cert_file() in main() before this
    # runs; surfacing it proves the frozen bundle can verify TLS for downloads.
    ssl_cert = os.environ.get("SSL_CERT_FILE")
    # configure_multiprocessing() should have replaced tqdm's mp lock with a
    # plain threading lock (no mp_lock attr) so no duplicate process spawns.
    tqdm_lock = getattr(sys.modules.get("tqdm"), "tqdm", None)
    tqdm_lock = getattr(tqdm_lock, "_lock", None) if tqdm_lock else None
    mp_guard = "ok" if (tqdm_lock is not None and not hasattr(tqdm_lock, "mp_lock")) else "off"
    print(
        f"SELFTEST OK ffmpeg={ffmpeg_path!r} "
        f"stems={len(registry.STEM_MODELS)} drums={len(registry.DRUM_MODELS)} "
        f"roformer_bs=ok roformer_mel=ok "
        f"ssl_cert={ssl_cert!r} mp_guard={mp_guard}"
    )
    return 0


def main() -> int:
    # Frozen bundles ship their own OpenSSL with no usable CA path; point it at
    # the bundled certifi store so weight downloads don't fail TLS verification.
    configure_ssl_cert_file()
    # Stop tqdm's mp lock from spawning a duplicate (empty) GUI window.
    configure_multiprocessing()
    app = QApplication.instance() or QApplication(sys.argv)
    # Expose the bundled ffmpeg on PATH once, before any separation runs.
    ffmpeg_path = audio.prepare_ffmpeg_path()
    window = MainWindow()
    window.show()
    if os.environ.get("BANDPREPARE_GUI_SELFTEST"):
        return _selftest(app, ffmpeg_path)
    return app.exec()
