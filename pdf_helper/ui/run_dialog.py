"""The modal dialog a job runs behind: progress and Cancel, then Done / Failed / Cancelled with OK."""

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RunDialog(QDialog):
    """Driven by the worker's signals only; never calls processEvents (the QProgressDialog trap)."""

    cancelled = Signal()  # Cancel, Esc or the title-bar X while running
    open_output = Signal()  # the Done-state button

    def __init__(self, parent: QWidget | None, title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(420)
        self._running = True

        self.status = QLabel("Working...")
        self.progress = QProgressBar(textVisible=False)
        self.progress.setRange(0, 0)  # busy until the first file reports
        self.details_button = QPushButton("Details", checkable=True)
        self.details = QPlainTextEdit(readOnly=True, maximumBlockCount=5000)
        self.details.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.details.hide()
        self.details_button.toggled.connect(self.details.setVisible)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.rejected.connect(self.reject)
        self.buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.details)
        layout.addWidget(self.buttons)

    def message(self, text: str) -> None:
        if text.startswith("ERROR"):
            red = self.palette().brightText().color().name()  # SystemFillColorCritical for this scheme
            self.details.appendHtml(f'<span style="color:{red};">{escape(text)}</span>')
            self.details_button.setChecked(True)  # a failure is shown, not hidden behind a click
        else:
            self.details.appendPlainText(text)

    def set_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.progress.setFormat("%v of %m")
        self.progress.setTextVisible(True)

    def finish(self, text: str, role: QPalette.ColorRole, has_outputs: bool) -> None:
        self._running = False
        self.status.setText(text)
        self.status.setForegroundRole(role)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.setTextVisible(False)
        self.buttons.clear()
        if has_outputs:
            open_button = self.buttons.addButton("Open output folder", QDialogButtonBox.ButtonRole.ActionRole)
            open_button.clicked.connect(self.open_output.emit)
        self.buttons.addButton(QDialogButtonBox.StandardButton.Ok).setDefault(True)

    def reject(self) -> None:
        if not self._running:
            super().reject()
            return
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel.isEnabled():  # a second Esc while cancelling asks nothing new
            cancel.setEnabled(False)
            self.status.setText("Cancelling after the current file...")
            self.cancelled.emit()
