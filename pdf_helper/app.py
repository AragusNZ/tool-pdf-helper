import logging
import sys
import tempfile
from functools import partial
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, Slot
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from pdf_helper import __version__
from pdf_helper.core.convert import supported_extensions
from pdf_helper.features import FEATURES
from pdf_helper.features.base import Feature, FeatureContext
from pdf_helper.ui.dialogs import open_file_paths
from pdf_helper.ui.file_queue import FileQueue
from pdf_helper.ui.theme import apply_scheme, asset_path
from pdf_helper.ui.worker import Worker

LOG_FILE = Path(tempfile.gettempdir()) / "PdfHelper.log"  # tracebacks land here; the exe has no console
GRID_COLUMNS = 4
log = logging.getLogger(__name__)


def settings() -> QSettings:
    return QSettings("pdf-helper", "PdfHelper")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PDF Helper {__version__}")
        self.resize(760, 620)
        self.setMinimumSize(640, 480)
        self._worker: Worker | None = None

        self.queue = FileQueue()
        self.queue.changed.connect(self._refresh_buttons)
        self.log_view = QPlainTextEdit(readOnly=True, maximumBlockCount=5000)
        self.log_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

        self._build_menus()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self._files_group(), stretch=3)
        layout.addWidget(self._actions_group())
        layout.addWidget(self._log_group(), stretch=2)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.progress = QProgressBar(maximumWidth=140, textVisible=False)
        self.progress.setRange(0, 0)  # indeterminate: features report no percentage
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        self._refresh_buttons()

    # --- construction ------------------------------------------------------
    def _files_group(self) -> QGroupBox:
        hint = QLabel("Drop files here, or drag to reorder.")
        hint.setEnabled(False)  # dimmed by the style rather than a hardcoded grey

        buttons = QHBoxLayout()
        for text, fn in (("Add files...", self._add_files), ("Remove", self.queue.remove_selected), ("Clear", self.queue.clear)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            buttons.addWidget(b)
        buttons.addStretch()

        inner = QVBoxLayout()
        inner.addWidget(hint)
        inner.addWidget(self.queue)
        inner.addLayout(buttons)
        group = QGroupBox("Files")
        group.setLayout(inner)
        return group

    def _actions_group(self) -> QGroupBox:
        self.feature_buttons: list[tuple[Feature, QPushButton]] = []
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, feature in enumerate(FEATURES):
            b = QPushButton(feature.label)
            b.setToolTip(feature.tooltip)
            b.clicked.connect(partial(self._run_feature, feature))
            grid.addWidget(b, i // GRID_COLUMNS, i % GRID_COLUMNS)
            self.feature_buttons.append((feature, b))
        for column in range(GRID_COLUMNS):
            grid.setColumnStretch(column, 1)  # equal-width buttons whatever the label length
        group = QGroupBox("Actions")
        group.setLayout(grid)
        return group

    def _log_group(self) -> QGroupBox:
        inner = QVBoxLayout()
        inner.addWidget(self.log_view)
        group = QGroupBox("Log")
        group.setLayout(inner)
        return group

    def _build_menus(self) -> None:
        theme_menu = self.menuBar().addMenu("&View").addMenu("&Theme")
        group = QActionGroup(self)
        current = settings().value("theme", "System")
        for name in ("System", "Light", "Dark"):
            action = QAction(name, self, checkable=True, checked=(name == current))
            action.triggered.connect(partial(self._set_theme, name))
            group.addAction(action)
            theme_menu.addAction(action)
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(QAction("&About", self, triggered=self._about))

    def _set_theme(self, name: str) -> None:
        settings().setValue("theme", name)
        apply_scheme(name)

    def _about(self) -> None:
        QMessageBox.about(self, "PDF Helper", f"PDF Helper {__version__}\n\nLog file: {LOG_FILE}")

    # --- queue -------------------------------------------------------------
    def _add_files(self) -> None:
        self._report_skipped(self.queue.add_paths(open_file_paths(self, supported_extensions())))

    def _report_skipped(self, skipped) -> None:
        for p in skipped:
            self.log(f"skipped unsupported file {p.name}")

    def _refresh_buttons(self) -> None:
        files = self.queue.paths()
        busy = self._worker is not None
        for feature, button in self.feature_buttons:
            button.setEnabled(not busy and feature.enabled_for(files))
        self.statusBar().showMessage("Working..." if busy else f"{len(files)} file(s) queued")

    # --- features ----------------------------------------------------------
    def _run_feature(self, feature: Feature) -> None:
        ctx = FeatureContext(files=self.queue.paths(), log=self.log, parent=self)
        params = None
        if feature.prepare is not None:
            try:
                params = feature.prepare(ctx)
            except Exception as exc:  # noqa: BLE001 - prepare opens the file; it may be corrupt or gone
                log.exception("%s prepare failed", feature.label)
                self.log(f"ERROR: {feature.label}: {exc or type(exc).__name__}")
                return
            if params is None:
                self.log(f"{feature.label}: cancelled")
                return
        self.log(f"--- {feature.label} ---")
        # Worker thread must not touch widgets: log via a queued signal, drop the parent widget.
        self._worker = Worker(lambda: feature.run(ctx, params), parent=self)
        ctx.log = self._worker.message.emit
        ctx.parent = None
        self._worker.message.connect(self.log)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._refresh_buttons()
        self.progress.show()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._worker.start()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.log(f"ERROR: {message} (details: {LOG_FILE})")

    @Slot()
    def _on_finished(self) -> None:
        QApplication.restoreOverrideCursor()
        self.progress.hide()
        self.log("done")
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self._refresh_buttons()

    def closeEvent(self, event: QCloseEvent) -> None:
        # Destroying a running QThread aborts the process; refuse to close until the job is done.
        if self._worker is not None:
            self.log("still working - wait for 'done' before closing")
            event.ignore()
        else:
            super().closeEvent(event)

    # --- logging -----------------------------------------------------------
    @Slot(str)
    def log(self, message: str) -> None:
        if message.startswith("ERROR"):
            # One red per scheme: the dark one would be muddy on white, the light one dim on black.
            red = "#ff6b6b" if self.palette().base().color().lightness() < 128 else "#c0272d"
            self.log_view.appendHtml(f'<span style="color:{red};">{escape(message)}</span>')
        else:
            self.log_view.appendPlainText(message)


def _excepthook(exc_type, exc, tb) -> None:
    logging.getLogger("pdf_helper").critical("unhandled exception", exc_info=(exc_type, exc, tb))
    QMessageBox.critical(None, "PDF Helper", f"{exc}\n\nDetails: {LOG_FILE}")


def main() -> None:
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = _excepthook
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(asset_path("icon.ico"))))
    app.setStyle("Fusion")  # same widget look on Windows and WSL; must precede apply_scheme
    apply_scheme(settings().value("theme", "System"))  # also installs the stylesheet
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
