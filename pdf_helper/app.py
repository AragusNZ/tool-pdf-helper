import logging
import logging.handlers
import sys
import tempfile
from functools import partial
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QTimer, QUrl, Slot
from PySide6.QtGui import (
    QAction, QActionGroup, QCloseEvent, QDesktopServices, QFont, QFontDatabase, QGuiApplication, QIcon, QKeySequence,
    QPalette, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QStyleFactory, QTabWidget, QVBoxLayout, QWidget,
)

from pdf_helper import __version__
from pdf_helper.core.convert import supported_extensions
from pdf_helper.core.update import RELEASES_URL, is_newer, latest_version
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
        if geometry := settings().value("geometry"):
            self.restoreGeometry(geometry)
        self._worker: Worker | None = None
        self._output_dir: Path | None = None
        self._update_worker: Worker | None = None

        self.queue = FileQueue()
        self.queue.changed.connect(self._refresh_buttons)
        self.log_view = QPlainTextEdit(readOnly=True, maximumBlockCount=5000)
        self.log_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

        self._build_menus()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)  # Fluent: 16epx surface to edge, 12 between cards
        layout.setSpacing(12)
        layout.addWidget(self._files_group(), stretch=3)
        layout.addWidget(self._actions_tabs())
        layout.addWidget(self._log_group(), stretch=2)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.progress = QProgressBar(maximumWidth=140, textVisible=False)
        self.progress.setRange(0, 0)  # indeterminate: features report no percentage
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.hide()
        self.statusBar().addPermanentWidget(self.cancel_button)
        self._refresh_buttons()

    # --- construction ------------------------------------------------------
    def _files_group(self) -> QGroupBox:
        hint = QLabel("Drop files here, or drag to reorder.")
        hint.setForegroundRole(QPalette.ColorRole.PlaceholderText)  # secondary text, not disabled text

        delete = QShortcut(QKeySequence.StandardKey.Delete, self.queue, activated=self.queue.remove_selected)
        delete.setContext(Qt.ShortcutContext.WidgetShortcut)  # only while the queue has focus

        buttons = QHBoxLayout()
        buttons.setSpacing(8)  # Fluent: 8epx between buttons
        for text, fn in (("Add files...", self._add_files), ("Remove", self.queue.remove_selected), ("Clear", self.queue.clear)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            buttons.addWidget(b)
        buttons.addStretch()

        inner = QVBoxLayout()
        inner.setSpacing(8)
        inner.addWidget(hint)
        inner.addWidget(self.queue)
        inner.addLayout(buttons)
        group = QGroupBox("Files")
        group.setLayout(inner)
        return group

    def _actions_tabs(self) -> QTabWidget:
        """One tab per feature group, in the order the registry first names it."""
        self.feature_buttons: list[tuple[Feature, QPushButton]] = []
        groups: dict[str, list[Feature]] = {}
        for feature in FEATURES:
            groups.setdefault(feature.group, []).append(feature)
        self.tabs = QTabWidget()
        for name, features in groups.items():
            grid = QGridLayout()
            grid.setSpacing(8)
            for i, feature in enumerate(features):
                b = QPushButton(feature.label)
                b.setToolTip(feature.tooltip)
                b.clicked.connect(partial(self._run_feature, feature))
                grid.addWidget(b, i // GRID_COLUMNS, i % GRID_COLUMNS)
                self.feature_buttons.append((feature, b))
            for column in range(GRID_COLUMNS):
                grid.setColumnStretch(column, 1)  # equal-width buttons whatever the label length
            page = QWidget()
            page.setLayout(grid)
            self.tabs.addTab(page, name)
        return self.tabs

    def _log_group(self) -> QGroupBox:
        self.open_output = QPushButton("Open output folder", enabled=False)
        self.open_output.clicked.connect(self._open_output)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.open_output)
        inner = QVBoxLayout()
        inner.addWidget(self.log_view)
        inner.addLayout(buttons)
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
        help_menu.addAction(QAction("Check for &Updates...", self, triggered=lambda: self._check_updates(manual=True)))
        self.startup_check = QAction("Check on &Startup", self, checkable=True, checked=check_on_startup())
        self.startup_check.toggled.connect(lambda on: settings().setValue("check_updates", on))
        help_menu.addAction(self.startup_check)
        help_menu.addSeparator()
        help_menu.addAction(QAction("&About", self, triggered=self._about))

    def _set_theme(self, name: str) -> None:
        settings().setValue("theme", name)
        apply_scheme(name)

    def _about(self) -> None:
        QMessageBox.about(self, "PDF Helper", f"PDF Helper {__version__}\n\nLog file: {LOG_FILE}")

    # --- updates -----------------------------------------------------------
    def _check_updates(self, manual: bool) -> None:
        """Ask GitHub off the UI thread; a startup check (manual=False) stays silent unless there is news."""
        if self._update_worker is not None:
            return
        result: dict = {}
        self._update_worker = Worker(lambda: result.update(latest=latest_version()), parent=self)
        if manual:
            self._update_worker.failed.connect(lambda m: self.log(f"ERROR: update check failed: {m}"))
        self._update_worker.finished.connect(lambda: self._on_update_checked(result.get("latest"), manual))
        self._update_worker.start()

    def _on_update_checked(self, latest: str | None, manual: bool) -> None:
        if self._update_worker is not None:
            self._update_worker.deleteLater()
        self._update_worker = None
        if latest is None:
            return  # failed: already logged if manual
        if is_newer(latest, __version__):
            answer = QMessageBox.question(
                self, "PDF Helper",
                f"PDF Helper {latest} is available (you have {__version__}).\n\nOpen the download page?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(RELEASES_URL))
        elif manual:
            QMessageBox.information(self, "PDF Helper", f"PDF Helper {__version__} is up to date.")

    # --- queue -------------------------------------------------------------
    def _add_files(self) -> None:
        paths = open_file_paths(self, supported_extensions(), settings().value("last_dir", ""))
        if paths:
            settings().setValue("last_dir", str(paths[0].parent))
        self._report_skipped(self.queue.add_paths(paths))

    def _report_skipped(self, skipped) -> None:
        for p in skipped:
            self.log(f"skipped {p.name}")  # unsupported, or gone since it was picked

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
        ctx.progress = self._worker.progress.emit
        ctx.cancelled = self._worker.isInterruptionRequested
        ctx.parent = None
        self._ctx = ctx
        self._worker.message.connect(self.log)
        self._worker.progress.connect(self._on_progress)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._refresh_buttons()
        self.progress.setRange(0, 0)  # busy until the first file reports
        self.progress.setTextVisible(False)
        self.progress.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._worker.start()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.log(f"ERROR: {message} (details: {LOG_FILE})")

    @Slot()
    def _on_finished(self) -> None:
        QApplication.restoreOverrideCursor()
        self.progress.hide()
        self.cancel_button.hide()
        self.log("done")
        if self._ctx.outputs:
            # ponytail: first output's folder only; Create PDF(s) across several source folders opens one of them.
            first = self._ctx.outputs[0]
            self._output_dir = first if first.is_dir() else first.parent
        self.open_output.setEnabled(self._output_dir is not None)
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self._refresh_buttons()

    @Slot(int, int)
    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.progress.setFormat("%v of %m")
        self.progress.setTextVisible(True)

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.log("cancelling after the current file...")

    def _open_output(self) -> None:
        if self._output_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._output_dir)))

    def closeEvent(self, event: QCloseEvent) -> None:
        # Destroying a running QThread aborts the process; refuse to close until the job is done.
        if self._worker is not None:
            self.log("still working - press Cancel or wait for 'done'")
            event.ignore()
        else:
            if self._update_worker is not None:
                self._update_worker.wait()  # bounded by the request timeout
            settings().setValue("geometry", self.saveGeometry())
            super().closeEvent(event)

    # --- logging -----------------------------------------------------------
    @Slot(str)
    def log(self, message: str) -> None:
        if message.startswith("ERROR"):
            red = self.palette().brightText().color().name()  # SystemFillColorCritical for this scheme
            self.log_view.appendHtml(f'<span style="color:{red};">{escape(message)}</span>')
        else:
            self.log_view.appendPlainText(message)


def check_on_startup() -> bool:
    return settings().value("check_updates", True, type=bool)


def _follow_system_scheme(_scheme) -> None:
    """Repaint when the OS flips light/dark, but only while the app is set to follow it."""
    if settings().value("theme", "System") == "System":
        apply_scheme("System")


def _excepthook(exc_type, exc, tb) -> None:
    logging.getLogger("pdf_helper").critical("unhandled exception", exc_info=(exc_type, exc, tb))
    QMessageBox.critical(None, "PDF Helper", f"{exc}\n\nDetails: {LOG_FILE}")


def main() -> None:
    handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=1, encoding="utf-8")
    logging.basicConfig(handlers=[handler], level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = _excepthook
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(asset_path("icon.ico"))))
    # The native Windows 11 style draws Fluent controls properly; Fusion is the fallback elsewhere.
    app.setStyle("windows11" if "windows11" in QStyleFactory.keys() else "Fusion")
    if "Segoe UI Variable Text" in QFontDatabase.families():
        font = QFont("Segoe UI Variable Text")
        font.setPointSizeF(10.5)  # Windows 11 Body: 14px regular
        app.setFont(font)
    apply_scheme(settings().value("theme", "System"))  # also installs the stylesheet
    QGuiApplication.styleHints().colorSchemeChanged.connect(_follow_system_scheme)
    window = MainWindow()
    window.show()
    # Files from Send To, "Open with" or the command line. arguments() has Qt's own flags stripped.
    window._report_skipped(window.queue.add_paths([Path(a) for a in app.arguments()[1:]]))
    if check_on_startup():
        QTimer.singleShot(1500, lambda: window._check_updates(manual=False))  # after the window has painted
    sys.exit(app.exec())
