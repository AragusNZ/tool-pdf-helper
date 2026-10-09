"""Stack several stamps on a page preview, then save once. The pending edits can be saved to a file and loaded back."""

import tempfile
from pathlib import Path

import pymupdf
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdf_helper.core.edit import EDITS_EXT, Op, apply_edits, describe, load_edits, save_edits
from pdf_helper.core.pages import parse_page_spec
from pdf_helper.core.pdf import page_count
from pdf_helper.core.render import render_page_png
from pdf_helper.core.stamp import NUMBER_FORMATS, NUMBER_POSITIONS
from pdf_helper.ui.dialogs import Namer, ask_options, ask_output, ask_text
from pdf_helper.ui.place_dialog import PlaceDialog
from pdf_helper.ui.preview import PagePreview, preview_px

Box = tuple[float, float, float, float]


class EditDialog(QDialog):
    """The preview shows the first queued PDF with every edit applied; the edits go onto every queued file.

    Save PDF... asks where to write before closing, so a cancelled file dialog keeps the edits.
    """

    def __init__(self, parent: QWidget | None, files: list[Path]):
        super().__init__(parent)
        self.files = files
        self.src = files[0]
        self.total = page_count(self.src)
        self.ops: list[Op] = []
        self.namer: Namer | None = None  # set by Save PDF...
        self._tmp = tempfile.TemporaryDirectory()
        self.finished.connect(lambda _code: self._tmp.cleanup())  # the dialog outlives exec() as a child of the window
        self.current = self.src  # the source, or the composed preview once there are edits
        self.setWindowTitle("Edit")

        batch = f" - edits apply to all {len(files)} queued files" if len(files) > 1 else ""
        heading = QLabel(self.src.name + batch)
        self.preview = PagePreview()
        self.page_box = QSpinBox(minimum=1, maximum=self.total, value=1, suffix=f" of {self.total}")
        self.page_box.valueChanged.connect(self._render)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._outline)
        self.delete_key = QShortcut(QKeySequence.StandardKey.Delete, self.list, activated=self._remove)
        self.delete_key.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.status = QLabel(wordWrap=True)

        form = QFormLayout()
        form.addRow("Preview page:", self.page_box)

        adds = QGridLayout()
        actions = (
            ("Add text...", lambda: self._place("text")), ("Add image...", lambda: self._place("image")),
            ("Page numbers...", self._add_numbers), ("Watermark...", self._add_watermark),
            ("Replace text...", self._add_replace),
        )
        for i, (text, fn) in enumerate(actions):
            b = QPushButton(text)
            b.clicked.connect(fn)
            adds.addWidget(b, i // 2, i % 2)

        self.remove = QPushButton("Remove", enabled=False)
        self.remove.clicked.connect(self._remove)
        self.up = QPushButton("Move up", enabled=False)
        self.up.clicked.connect(lambda: self._move(-1))
        self.down = QPushButton("Move down", enabled=False)
        self.down.clicked.connect(lambda: self._move(1))
        self.save_button = QPushButton("Save edits...", enabled=False)
        self.save_button.clicked.connect(self._save_edits)
        load = QPushButton("Load edits...")
        load.clicked.connect(self._load_edits)
        order = QHBoxLayout()
        for b in (self.remove, self.up, self.down):
            order.addWidget(b)
        order.addStretch()
        files_row = QHBoxLayout()
        files_row.addStretch()
        files_row.addWidget(self.save_button)
        files_row.addWidget(load)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Save PDF...")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        side = QVBoxLayout()
        side.addLayout(form)
        side.addLayout(adds)
        side.addWidget(QLabel("Edits, applied in this order:"))
        side.addWidget(self.list)
        side.addLayout(order)
        side.addLayout(files_row)
        side.addWidget(self.status)
        side.addWidget(self.buttons)
        panel = QWidget(maximumWidth=340)
        panel.setLayout(side)
        left = QVBoxLayout()
        left.addWidget(heading)
        left.addWidget(self.preview)
        layout = QHBoxLayout()
        layout.addLayout(left)
        layout.addWidget(panel)
        self.setLayout(layout)

        self._refresh()

    # --- edits -------------------------------------------------------------
    def _compose(self, ops: list[Op]) -> list[str]:
        if not ops:
            self.current = self.src
            return []
        out = Path(self._tmp.name) / f"{len(ops)}.pdf"
        notes = apply_edits(self.src, out, ops)
        self.current = out
        return notes

    def _set(self, ops: list[Op], what: str = "", row: int | None = None) -> bool:
        """Make ``ops`` the edit list if every one applies to the source; otherwise say why and change nothing.

        ``what`` names the edit being added, for the message. ``row`` is the row to leave selected (default: last).
        """
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            notes = self._compose(ops)
        except Exception as exc:  # a bad page spec, a missing image, a malformed edits file: user input
            message = str(exc) or type(exc).__name__
            self.status.setText(f"{what}: {message}" if what else message)
            return False
        finally:
            QApplication.restoreOverrideCursor()
        self.ops = ops
        self.status.setText(f"{'; '.join(notes)} in {self.src.name}" if notes else "")
        self._refresh(row)
        return True

    def _refresh(self, row: int | None = None) -> None:
        self.list.clear()
        self.list.addItems([describe(op) for op in self.ops])
        self.list.setCurrentRow(len(self.ops) - 1 if row is None else row)
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        for widget in (self.remove, self.up, self.down, self.save_button, ok):
            widget.setEnabled(bool(self.ops))
        self._render()

    def _render(self) -> None:
        png, width, _ = render_page_png(self.current, self.page_box.value() - 1, max_px=preview_px(self))
        self.preview.show_page(png, width)
        self._outline()

    def _box(self, op: Op | None) -> Box | None:
        """Where a text or image edit lands on the previewed page, or None for the other kinds and other pages."""
        if op is None or op["kind"] not in ("text", "image"):
            return None
        if op["pages"] and self.page_box.value() - 1 not in parse_page_spec(op["pages"], self.total):
            return None
        if op["kind"] == "image":
            return tuple(op["rect"])
        x, y = op["pos"]
        return (x, y, x + pymupdf.Font(op["font"]).text_length(op["text"], op["size"]), y + op["size"])

    def _outline(self) -> None:
        row = self.list.currentRow()
        box = self._box(self.ops[row] if 0 <= row < len(self.ops) else None)
        self.preview.draw_boxes([box] if box else [])

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self._set(self.ops[:row] + self.ops[row + 1:], row=min(row, len(self.ops) - 2))

    def _move(self, delta: int) -> None:
        row, new = self.list.currentRow(), self.list.currentRow() + delta
        if 0 <= row < len(self.ops) and 0 <= new < len(self.ops):
            ops = list(self.ops)
            ops[row], ops[new] = ops[new], ops[row]
            self._set(ops, row=new)

    def _add(self, op: Op) -> bool:
        return self._set([*self.ops, op], describe(op))

    # --- adding ------------------------------------------------------------
    def _place(self, mode: str) -> None:
        # Placed on the composed page, so it sits over earlier edits; images are browsed from beside the real file.
        dialog = PlaceDialog(self, self.current, mode, start=self.src.parent)
        dialog.page_box.setValue(self.page_box.value())
        if dialog.exec():
            self._add(dialog.op())

    def _add_numbers(self) -> None:
        answers = ask_options(self, "Page numbers", {"Show": list(NUMBER_FORMATS), "Position": list(NUMBER_POSITIONS)})
        if answers is not None:
            self._add({"kind": "numbers", "fmt": NUMBER_FORMATS[answers["Show"]], "position": answers["Position"]})

    def _add_watermark(self) -> None:
        text = (ask_text(self, "Watermark", "Watermark text:") or "").strip()
        if text:
            self._add({"kind": "watermark", "text": text})

    def _add_replace(self) -> None:
        answers = ask_options(self, "Replace text", {"Find": "", "Replace with": "", "Match case": False})
        old = str(answers["Find"]).strip() if answers is not None else ""
        if old:
            self._add({"kind": "replace", "old": old, "new": answers["Replace with"], "case_sensitive": answers["Match case"]})

    # --- edits file --------------------------------------------------------
    def _save_edits(self) -> None:
        suggested = self.src.with_name(self.src.stem + EDITS_EXT)
        name, _ = QFileDialog.getSaveFileName(self, "Save edits", str(suggested), f"Edits (*{EDITS_EXT})")
        if name:
            save_edits(Path(name if name.endswith(EDITS_EXT) else name + EDITS_EXT), self.ops)

    def _load_edits(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Load edits", str(self.src.parent), f"Edits (*{EDITS_EXT})")
        if not name:
            return
        try:
            ops = load_edits(Path(name))
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        for op in ops:  # one at a time, so the ones before a bad one still land
            if not self._add(op):
                break

    # --- closing -----------------------------------------------------------
    def accept(self) -> None:
        self.namer = ask_output(self, self.files, "-edited")
        if self.namer is not None:
            super().accept()

    def reject(self) -> None:
        if self.ops:
            answer = QMessageBox.question(self, "Edit", f"Discard {len(self.ops)} edit(s)?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        super().reject()
