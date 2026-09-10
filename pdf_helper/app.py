import logging
import sys
import tempfile
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from pdf_helper import __version__
from pdf_helper.core.convert import supported_extensions
from pdf_helper.features import FEATURES
from pdf_helper.features.base import Feature, FeatureContext
from pdf_helper.ui.dialogs import open_file_paths
from pdf_helper.ui.file_queue import FileQueue
from pdf_helper.ui.worker import Worker

LOG_FILE = Path(tempfile.gettempdir()) / "PdfHelper.log"  # tracebacks land here; the exe has no console
log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PDF Helper {__version__}")
        self.resize(720, 560)
        self._worker: Worker | None = None

        self.queue = FileQueue()
        self.queue.changed.connect(self._refresh_buttons)
        self.log_view = QPlainTextEdit(readOnly=True, maximumBlockCount=5000)

        queue_buttons = QHBoxLayout()
        for text, fn in (("Add files...", self._add_files), ("Remove", self.queue.remove_selected), ("Clear", self.queue.clear)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            queue_buttons.addWidget(b)
        queue_buttons.addStretch()

        self.feature_buttons: list[tuple[Feature, QPushButton]] = []
        feature_grid = QGridLayout()
        for i, feature in enumerate(FEATURES):
            b = QPushButton(feature.label)
            b.setToolTip(feature.tooltip)
            b.clicked.connect(partial(self._run_feature, feature))
            feature_grid.addWidget(b, i // 4, i % 4)
            self.feature_buttons.append((feature, b))

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Drop files here (drag to reorder):"))
        layout.addWidget(self.queue, stretch=3)
        layout.addLayout(queue_buttons)
        layout.addLayout(feature_grid)
        layout.addWidget(self.log_view, stretch=2)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)
        self._refresh_buttons()

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
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._worker.start()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.log(f"ERROR: {message} (details: {LOG_FILE})")

    @Slot()
    def _on_finished(self) -> None:
        QApplication.restoreOverrideCursor()
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
        self.log_view.appendPlainText(message)


def _excepthook(exc_type, exc, tb) -> None:
    logging.getLogger("pdf_helper").critical("unhandled exception", exc_info=(exc_type, exc, tb))
    QMessageBox.critical(None, "PDF Helper", f"{exc}\n\nDetails: {LOG_FILE}")


def main() -> None:
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = _excepthook
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
