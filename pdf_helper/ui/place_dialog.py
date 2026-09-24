"""Click-on-the-page placement dialog, shared by Add text and Add image."""

from pathlib import Path

import pymupdf
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from pdf_helper.core.convert import IMAGE_EXTS
from pdf_helper.core.pages import parse_page_spec
from pdf_helper.core.pdf import page_count
from pdf_helper.core.render import render_page_png
from pdf_helper.core.stamp import MM, fonts, image_size

OUTLINE = QColor("#c0272d")


class _Preview(QLabel):
    """Page image that reports clicks in page points."""

    clicked = Signal(float, float)

    def __init__(self):
        super().__init__(alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.base: QPixmap | None = None
        self._scale = 1.0

    def show_page(self, png: bytes, page_width: float) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(png, "PNG")
        self.base = pixmap
        self._scale = pixmap.width() / page_width
        self.setPixmap(pixmap)

    def draw_box(self, rect: tuple[float, float, float, float] | None) -> None:
        """Redraw the page with ``rect`` (page points) outlined, or plain when None."""
        if self.base is None:
            return
        pixmap = self.base.copy()
        if rect is not None:
            painter = QPainter(pixmap)
            painter.setPen(QPen(OUTLINE, 2))
            s = self._scale
            painter.drawRect(round(rect[0] * s), round(rect[1] * s), round((rect[2] - rect[0]) * s), round((rect[3] - rect[1]) * s))
            painter.end()
        self.setPixmap(pixmap)

    def mousePressEvent(self, event) -> None:
        # A click past the page image (the dialog is resizable) is not a point on the page.
        if self.base is not None:
            point = event.position()
            if self.base.rect().contains(point.toPoint()):
                self.clicked.emit(point.x() / self._scale, point.y() / self._scale)


class PlaceDialog(QDialog):
    """Pick a point on a page plus the text or image to put there.

    ``mode`` is "text" or "image". The preview shows the first queued PDF; the chosen point and
    page spec are applied to every queued file.
    """

    def __init__(self, parent: QWidget | None, src: Path, mode: str):
        super().__init__(parent)
        self.mode = mode
        self.src = src
        self.total = page_count(src)
        self.point: tuple[float, float] | None = None
        self.colour = QColor("black")
        self._aspect = 1.0  # image height / width
        self.setWindowTitle("Add text" if mode == "text" else "Add image")

        self.preview = _Preview()
        self.preview.clicked.connect(self._on_click)
        self.page_box = QSpinBox(minimum=1, maximum=self.total, value=1)
        self.page_box.valueChanged.connect(self._render)
        self.spec = QLineEdit("1")
        self._spec_edited = False  # once the user types a spec, stop following the preview page
        self.spec.textEdited.connect(lambda: setattr(self, "_spec_edited", True))
        self.position = QLabel("click the page")
        self.error = QLabel(wordWrap=True)

        form = QFormLayout()
        form.addRow("Preview page:", self.page_box)
        if mode == "text":
            self._add_text_rows(form)
        else:
            self._add_image_rows(form)
        form.addRow("Apply to pages:", self.spec)
        form.addRow("Position:", self.position)
        self.spec.setToolTip(f"1-{self.total}, e.g. 1-3,5; blank = all pages")

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)

        side = QVBoxLayout()
        side.addLayout(form)
        side.addWidget(self.error)
        side.addStretch()
        side.addWidget(self.buttons)
        panel = QWidget(maximumWidth=320)
        panel.setLayout(side)
        layout = QHBoxLayout()
        layout.addWidget(self.preview)
        layout.addWidget(panel)
        self.setLayout(layout)

        self._render()
        self._update_ok()

    # --- construction ------------------------------------------------------
    def _add_text_rows(self, form: QFormLayout) -> None:
        self.text = QLineEdit()
        self.text.textChanged.connect(self._changed)
        self.font = QComboBox()
        for code, name in sorted(fonts().items(), key=lambda item: item[1]):
            self.font.addItem(name, code)
        self.font.setCurrentIndex(self.font.findData("helv"))
        self.font.currentIndexChanged.connect(self._changed)
        self.size = QSpinBox(minimum=6, maximum=200, value=24, suffix=" pt")
        self.size.valueChanged.connect(self._changed)
        self.colour_button = QPushButton(self.colour.name())
        self.colour_button.clicked.connect(self._pick_colour)
        form.addRow("Text:", self.text)
        form.addRow("Font:", self.font)
        form.addRow("Size:", self.size)
        form.addRow("Colour:", self.colour_button)

    def _add_image_rows(self, form: QFormLayout) -> None:
        self.image = QLineEdit(readOnly=True)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._pick_image)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.image)
        row.addWidget(browse)
        holder = QWidget()
        holder.setLayout(row)
        self.width_mm = QDoubleSpinBox(minimum=1.0, maximum=1000.0, value=50.0, decimals=1, suffix=" mm")
        self.width_mm.valueChanged.connect(self._changed)
        form.addRow("Image:", holder)
        form.addRow("Width:", self.width_mm)

    # --- interaction -------------------------------------------------------
    def _render(self) -> None:
        if not self._spec_edited:
            self.spec.setText(str(self.page_box.value()))
        png, width, _ = render_page_png(self.src, self.page_box.value() - 1)
        self.preview.show_page(png, width)
        self._changed()

    def _on_click(self, x: float, y: float) -> None:
        self.point = (x, y)
        self.position.setText(f"{x / MM:.0f}, {y / MM:.0f} mm from top-left")
        self._changed()

    def _changed(self) -> None:
        self.preview.draw_box(self.box())
        self._update_ok()

    def _pick_colour(self) -> None:
        chosen = QColorDialog.getColor(self.colour, self, "Text colour")
        if chosen.isValid():
            self.colour = chosen
            self.colour_button.setText(chosen.name())
            self._changed()

    def _pick_image(self) -> None:
        pattern = " ".join(f"*{e}" for e in sorted(IMAGE_EXTS))
        name, _ = QFileDialog.getOpenFileName(self, "Choose image", str(self.src.parent), f"Images ({pattern})")
        if not name:
            return
        try:
            width, height = image_size(Path(name))
        except Exception as exc:  # noqa: BLE001 - an unreadable or non-raster file is user input
            self.error.setText(f"cannot read {Path(name).name}: {exc}")
            return
        self._aspect = height / width
        self.image.setText(name)
        self.error.clear()
        self._changed()

    def _update_ok(self) -> None:
        ready = self.point is not None and self.box() is not None
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready)

    def _accept(self) -> None:
        spec = self.spec.text().strip()
        if spec:
            try:
                parse_page_spec(spec, self.total)
            except ValueError as exc:
                self.error.setText(f"Pages: {exc}")
                return
        self.accept()

    # --- results -----------------------------------------------------------
    def box(self) -> tuple[float, float, float, float] | None:
        """The placement rectangle in page points, or None while the choice is incomplete."""
        if self.point is None:
            return None
        x, y = self.point
        if self.mode == "text":
            text, size = self.text.text(), self.size.value()
            if not text:
                return None
            width = pymupdf.Font(self.font.currentData()).text_length(text, size)
            return (x, y, x + width, y + size)
        if not self.image.text():
            return None
        width = self.width_mm.value() * MM
        return (x, y, x + width, y + width * self._aspect)

    def params(self) -> tuple:
        """Feature parameters: text mode (text, point, spec, font, size, rgb); image mode (path, rect, spec)."""
        spec = self.spec.text().strip()
        if self.mode == "text":
            rgb = (self.colour.redF(), self.colour.greenF(), self.colour.blueF())
            return (self.text.text(), self.point, spec, self.font.currentData(), self.size.value(), rgb)
        return (Path(self.image.text()), self.box(), spec)
