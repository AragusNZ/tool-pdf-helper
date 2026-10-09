"""Stack several stamps on a page preview, then save once. The pending edits can be saved to a file and loaded back."""

import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QListWidget, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from pdf_helper.core.edit import EDITS_EXT, Op, apply_edits, describe, load_edits, save_edits
from pdf_helper.core.pdf import page_count
from pdf_helper.core.render import render_page_png
from pdf_helper.core.stamp import NUMBER_FORMATS, NUMBER_POSITIONS
from pdf_helper.ui.dialogs import ask_options, ask_text
from pdf_helper.ui.place_dialog import PlaceDialog
from pdf_helper.ui.preview import PagePreview, preview_px


class EditDialog(QDialog):
    """The preview shows the first queued PDF with every edit applied; the edits go onto every queued file."""

    def __init__(self, parent: QWidget | None, src: Path):
        super().__init__(parent)
        self.src = src
        self.total = page_count(src)
        self.ops: list[Op] = []
        self._tmp = tempfile.TemporaryDirectory()
        self.current = src  # the source, or the composed preview once there are edits
        self.setWindowTitle("Edit")

        self.preview = PagePreview()
        self.page_box = QSpinBox(minimum=1, maximum=self.total, value=1)
        self.page_box.valueChanged.connect(self._render)
        self.list = QListWidget()
        self.error = QLabel(wordWrap=True)

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
        self.save_button = QPushButton("Save edits...", enabled=False)
        self.save_button.clicked.connect(self._save_edits)
        load = QPushButton("Load edits...")
        load.clicked.connect(self._load_edits)
        files = QHBoxLayout()
        files.addWidget(self.remove)
        files.addStretch()
        files.addWidget(self.save_button)
        files.addWidget(load)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Save PDF...")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        side = QVBoxLayout()
        side.addLayout(form)
        side.addLayout(adds)
        side.addWidget(QLabel("Edits, applied in this order:"))
        side.addWidget(self.list)
        side.addLayout(files)
        side.addWidget(self.error)
        side.addWidget(self.buttons)
        panel = QWidget(maximumWidth=340)
        panel.setLayout(side)
        layout = QHBoxLayout()
        layout.addWidget(self.preview)
        layout.addWidget(panel)
        self.setLayout(layout)

        self._refresh()

    # --- edits -------------------------------------------------------------
    def _compose(self, ops: list[Op]) -> None:
        if ops:
            out = Path(self._tmp.name) / f"{len(ops)}.pdf"
            apply_edits(self.src, out, ops)
            self.current = out
        else:
            self.current = self.src

    def _set(self, ops: list[Op]) -> bool:
        """Make ``ops`` the edit list if every one applies to the source; otherwise say why and change nothing."""
        try:
            self._compose(ops)
        except Exception as exc:  # noqa: BLE001 - a bad page spec, a missing image, a malformed edits file: user input
            self.error.setText(str(exc) or type(exc).__name__)
            return False
        self.ops = ops
        self.error.clear()
        self._refresh()
        return True

    def _refresh(self) -> None:
        self.list.clear()
        self.list.addItems([describe(op) for op in self.ops])
        self.list.setCurrentRow(len(self.ops) - 1)
        for widget in (self.remove, self.save_button, self.buttons.button(QDialogButtonBox.StandardButton.Ok)):
            widget.setEnabled(bool(self.ops))
        self._render()

    def _render(self) -> None:
        png, width, _ = render_page_png(self.current, self.page_box.value() - 1, max_px=preview_px(self))
        self.preview.show_page(png, width)

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self._set(self.ops[:row] + self.ops[row + 1:])

    # --- adding ------------------------------------------------------------
    def _place(self, mode: str) -> None:
        dialog = PlaceDialog(self, self.current, mode)  # placed on the composed page, so it sits over earlier edits
        dialog.page_box.setValue(self.page_box.value())
        if dialog.exec():
            self._set([*self.ops, dialog.op()])

    def _add_numbers(self) -> None:
        answers = ask_options(self, "Page numbers", {"Show": list(NUMBER_FORMATS), "Position": list(NUMBER_POSITIONS)})
        if answers is not None:
            self._set([*self.ops, {"kind": "numbers", "fmt": NUMBER_FORMATS[answers["Show"]], "position": answers["Position"]}])

    def _add_watermark(self) -> None:
        text = (ask_text(self, "Watermark", "Watermark text:") or "").strip()
        if text:
            self._set([*self.ops, {"kind": "watermark", "text": text}])

    def _add_replace(self) -> None:
        answers = ask_options(self, "Replace text", {"Find": "", "Replace with": "", "Match case": False})
        old = str(answers["Find"]).strip() if answers is not None else ""
        if old:
            op = {"kind": "replace", "old": old, "new": answers["Replace with"], "case_sensitive": answers["Match case"]}
            self._set([*self.ops, op])

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
        except Exception as exc:  # noqa: BLE001 - not JSON, not a list, unknown kind: all the file's fault
            self.error.setText(str(exc) or type(exc).__name__)
            return
        for op in ops:  # one at a time, so the ones before a bad one still land
            if not self._set([*self.ops, op]):
                break

    # --- closing -----------------------------------------------------------
    def reject(self) -> None:
        if self.ops:
            answer = QMessageBox.question(self, "Edit", f"Discard {len(self.ops)} edit(s)?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        super().reject()
