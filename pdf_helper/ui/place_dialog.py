"""Click-on-the-page placement dialog: Edit > Add text and Add image."""

from pathlib import Path

import pymupdf
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdf_helper.core.convert import IMAGE_EXTS
from pdf_helper.core.pages import parse_page_spec
from pdf_helper.core.pdf import page_count
from pdf_helper.core.render import render_page_png
from pdf_helper.core.stamp import MM, fonts, image_size, stamp_image, stamp_text
from pdf_helper.ui.preview import PagePreview, preview_px


class PlaceDialog(QDialog):
    """Pick a point on a page plus the text or image to put there.

    ``mode`` is "text" or "image". The preview shows the first queued PDF with the text or image drawn on it as
    the output will have it; click to place, drag it to move it. The point and page spec apply to every queued file.
    """

    def __init__(self, parent: QWidget | None, src: Path, mode: str, start: Path | None = None):
        super().__init__(parent)
        self.mode = mode
        self.src = src
        self.start = start or src.parent  # where Browse... opens; the editor previews a temp file, so it says
        self.total = page_count(src)
        self.point: tuple[float, float] | None = None
        self.colour = QColor("black")
        self._aspect = 1.0  # image height / width
        self._grab = (0.0, 0.0)  # where inside the placed box a drag picked it up
        self._fits = True  # the last render managed to draw the text at that spot
        self._timer = QTimer(self, singleShot=True, interval=50)  # coalesce keystrokes and drag moves into ~20 renders/s
        self._timer.timeout.connect(self._render)
        self.setWindowTitle("Add text" if mode == "text" else "Add image")

        self.preview = PagePreview()
        self.preview.clicked.connect(self._on_click)
        self.preview.dragged.connect(self._on_drag)
        self.page_box = QSpinBox(minimum=1, maximum=self.total, value=1, suffix=f" of {self.total}")
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
        """Draw the page with the text or image on it, as the output will have it. The red box is the grab handle."""
        if not self._spec_edited:
            self.spec.setText(str(self.page_box.value()))
        page, max_px, box = self.page_box.value() - 1, preview_px(self), self.box()
        self._fits = True
        try:
            png, width, _ = render_page_png(self.src, page, max_px=max_px, stamp=self._stamp() if box else None)
        except ValueError as exc:  # it does not fit there: show the bare page and say why
            self._fits = False
            self.error.setText(str(exc))
            png, width, _ = render_page_png(self.src, page, max_px=max_px)
        else:
            if box:
                self.error.clear()
        self.preview.show_page(png, width)
        self.preview.draw_boxes([box] if box else [])
        self._update_ok()

    def _stamp(self):
        """What the preview draws: the same page-level call the output is made with."""
        if self.mode == "text":
            rgb = (self.colour.redF(), self.colour.greenF(), self.colour.blueF())
            font, size, text = self.font.currentData(), self.size.value(), self.text.text()
            return lambda page: stamp_text(page, text, self.point, fontname=font, size=size, color=rgb)
        return lambda page: stamp_image(page, Path(self.image.text()), self.box())

    def _on_click(self, x: float, y: float) -> None:
        box = self.box()
        if box and box[0] <= x <= box[2] and box[1] <= y <= box[3]:
            self._grab = (x - box[0], y - box[1])  # picked up where it sits, so a drag moves it without a jump
            return
        self._grab = (0.0, 0.0)
        self._move_to(x, y)

    def _on_drag(self, x: float, y: float) -> None:
        self._move_to(x - self._grab[0], y - self._grab[1])

    def _move_to(self, x: float, y: float) -> None:
        self.point = (max(x, 0.0), max(y, 0.0))
        self.position.setText(f"{self.point[0] / MM:.0f}, {self.point[1] / MM:.0f} mm from top-left")
        self._changed()

    def _changed(self) -> None:
        self._update_ok()
        if not self._timer.isActive():
            self._timer.start()

    def _pick_colour(self) -> None:
        chosen = QColorDialog.getColor(self.colour, self, "Text colour")
        if chosen.isValid():
            self.colour = chosen
            self.colour_button.setText(chosen.name())
            self._changed()

    def _pick_image(self) -> None:
        pattern = " ".join(f"*{e}" for e in sorted(IMAGE_EXTS))
        name, _ = QFileDialog.getOpenFileName(self, "Choose image", str(self.start), f"Images ({pattern})")
        if not name:
            return
        try:
            width, height = image_size(Path(name))
        except Exception as exc:
            self.error.setText(f"cannot read {Path(name).name}: {exc}")
            return
        self._aspect = height / width
        self.image.setText(name)
        self.error.clear()
        self._changed()

    def _update_ok(self) -> None:
        ready = self.point is not None and self.box() is not None and self._fits
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

    def op(self) -> dict:
        """The edit this dialog describes, JSON-ready: see ``core.edit``."""
        spec = self.spec.text().strip()
        if self.mode == "text":
            colour = [self.colour.redF(), self.colour.greenF(), self.colour.blueF()]
            return {"kind": "text", "text": self.text.text(), "pos": list(self.point), "pages": spec,
                    "font": self.font.currentData(), "size": self.size.value(), "color": colour}
        return {"kind": "image", "image": self.image.text(), "rect": list(self.box()), "pages": spec}
