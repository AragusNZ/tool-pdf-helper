"""Drag boxes over a page, and/or name a phrase, then take both out of the document for good."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from pdf_helper.core.pdf import page_count
from pdf_helper.core.render import render_page_png
from pdf_helper.ui.preview import PagePreview

MIN_SIDE = 3.0  # page points; anything smaller was a stray click, not a box
FILL = QColor(0, 0, 0, 120)

Box = tuple[float, float, float, float]


class DragPreview(PagePreview):
    """Page preview that turns a drag into a rectangle in page points."""

    dragged = Signal(float, float, float, float)

    def __init__(self):
        super().__init__()
        self._start: tuple[float, float] | None = None
        self.fixed: list[Box] = []  # boxes already kept on this page

    @staticmethod
    def _rect(start: tuple[float, float], now: tuple[float, float]) -> Box:
        x0, x1 = sorted((start[0], now[0]))
        y0, y1 = sorted((start[1], now[1]))
        return (x0, y0, x1, y1)

    def mousePressEvent(self, event) -> None:
        self._start = self.point_on_page(event.position())

    def mouseMoveEvent(self, event) -> None:
        now = self.clamped_point(event.position())
        if self._start is not None and now is not None:
            self.draw_boxes([*self.fixed, self._rect(self._start, now)], FILL)

    def mouseReleaseEvent(self, event) -> None:
        start, self._start = self._start, None
        now = self.clamped_point(event.position())
        if start is None or now is None:
            return
        rect = self._rect(start, now)
        if rect[2] - rect[0] < MIN_SIDE or rect[3] - rect[1] < MIN_SIDE:
            self.draw_boxes(self.fixed, FILL)  # a click: drop the rubber band
        else:
            self.dragged.emit(*rect)


class RedactDialog(QDialog):
    """Boxes are dragged on the first queued PDF; they and the phrase apply to every queued file."""

    def __init__(self, parent: QWidget | None, src: Path):
        super().__init__(parent)
        self.src = src
        self.total = page_count(src)
        self.boxes: dict[int, list[Box]] = {}
        self.setWindowTitle("Redact")

        self.preview = DragPreview()
        self.preview.dragged.connect(self._add_box)
        self.page_box = QSpinBox(minimum=1, maximum=self.total, value=1)
        self.page_box.valueChanged.connect(self._render)
        self.find = QLineEdit()
        self.find.textChanged.connect(self._update_ok)
        self.match_case = QCheckBox("Match case")
        self.count = QLabel()

        form = QFormLayout()
        form.addRow("Preview page:", self.page_box)
        form.addRow("Also remove:", self.find)
        form.addRow("", self.match_case)
        form.addRow("Boxes:", self.count)
        self.find.setToolTip("Every occurrence of this text goes, on every page of every queued file")

        undo = QPushButton("Undo box")
        undo.clicked.connect(self._undo)
        clear = QPushButton("Clear page")
        clear.clicked.connect(self._clear_page)
        row = QHBoxLayout()
        row.addWidget(undo)
        row.addWidget(clear)
        row.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        side = QVBoxLayout()
        side.addLayout(form)
        side.addLayout(row)
        side.addWidget(QLabel("Drag on the page to box out an area.", wordWrap=True))
        side.addStretch()
        side.addWidget(self.buttons)
        panel = QWidget(maximumWidth=320)
        panel.setLayout(side)
        layout = QHBoxLayout()
        layout.addWidget(self.preview)
        layout.addWidget(panel)
        self.setLayout(layout)

        self._render()

    # --- interaction -------------------------------------------------------
    def _page(self) -> int:
        return self.page_box.value() - 1

    def _render(self) -> None:
        png, width, _ = render_page_png(self.src, self._page())
        self.preview.show_page(png, width)
        self._refresh()

    def _refresh(self) -> None:
        here = self.boxes.get(self._page(), [])
        self.preview.fixed = here
        self.preview.draw_boxes(here, FILL)
        total = sum(len(v) for v in self.boxes.values())
        self.count.setText(f"{len(here)} on this page, {total} in all")
        self._update_ok()

    def _add_box(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.boxes.setdefault(self._page(), []).append((x0, y0, x1, y1))
        self._refresh()

    def _undo(self) -> None:
        here = self.boxes.get(self._page())
        if here:
            here.pop()
            self._refresh()

    def _clear_page(self) -> None:
        self.boxes.pop(self._page(), None)
        self._refresh()

    def _update_ok(self) -> None:
        ready = any(self.boxes.values()) or bool(self.find.text())
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready)

    # --- results -----------------------------------------------------------
    def params(self) -> tuple[dict[int, list[Box]], str, bool]:
        """Feature parameters: boxes by 0-based page, the phrase to remove, and whether case counts."""
        return ({k: v for k, v in self.boxes.items() if v}, self.find.text(), self.match_case.isChecked())
