from collections.abc import Callable
from pathlib import Path

from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QWidget,
)

from pdf_helper.core.pages import parse_page_spec
from pdf_helper.core.paths import fresh


def save_pdf_path(parent: QWidget | None, suggested: Path, ext: str = ".pdf") -> Path | None:
    kind = ext[1:].upper()
    name, _ = QFileDialog.getSaveFileName(parent, f"Save {kind}", str(suggested), f"{kind} (*{ext})")
    if not name:
        return None
    path = Path(name)
    return path if path.suffix.lower() == ext else path.with_suffix(ext)


Namer = Callable[[Path], Path]  # source file -> where its output goes


def ask_output(parent: QWidget | None, files: list[Path], suffix: str, ext: str = ".pdf") -> Namer | None:
    """Where a run writes. One file: a Save dialog. Several: a folder, then a suffix added to each source name.

    Returns source -> output path (no Qt inside, safe on the worker), or None when cancelled."""
    if len(files) == 1:
        out = save_pdf_path(parent, files[0].with_name(f"{files[0].stem}{suffix}{ext}"), ext)
        return None if out is None else lambda src: out
    out_dir = choose_directory(parent, files[0].parent)
    if out_dir is None:
        return None
    added = ask_text(parent, "Output names", f"Added to each file name, e.g. {files[0].stem}{suffix}{ext}:", suffix)
    return None if added is None else lambda src: fresh(out_dir / f"{src.stem}{added}{ext}")


def open_file_paths(parent: QWidget | None, exts: frozenset[str], start: str = "") -> list[Path]:
    pattern = " ".join(f"*{e}" for e in sorted(exts))
    names, _ = QFileDialog.getOpenFileNames(parent, "Add files", start, f"Supported ({pattern});;All files (*)")
    return [Path(n) for n in names]


def ask_text(parent: QWidget | None, title: str, prompt: str, default: str = "") -> str | None:
    text, ok = QInputDialog.getText(parent, title, prompt, QLineEdit.EchoMode.Normal, default)
    return text if ok else None


def choose_directory(parent: QWidget | None, start: Path) -> Path | None:
    name = QFileDialog.getExistingDirectory(parent, "Choose output folder", str(start))
    return Path(name) if name else None


def ask_int(parent: QWidget | None, title: str, prompt: str, default: int, lo: int, hi: int) -> int | None:
    value, ok = QInputDialog.getInt(parent, title, prompt, default, lo, hi)
    return value if ok else None


def ask_choice(parent: QWidget | None, title: str, prompt: str, options: list[str]) -> str | None:
    value, ok = QInputDialog.getItem(parent, title, prompt, options, 0, False)
    return value if ok else None


def ask_page_spec(
    parent: QWidget | None, title: str, total: int, log: Callable[[str], None], *, allow_blank: bool = False
) -> list[int] | None:
    """Ask for a page spec until it parses. None when cancelled, [] for a blank spec meaning all pages."""
    hint = ""
    tail = "; blank = all" if allow_blank else ", 8-"
    while True:
        spec = ask_text(parent, title, f"{hint}Pages (1-{total}, e.g. 1-3,5{tail}):")
        if spec is None:
            return None
        if allow_blank and not spec.strip():
            return []
        try:
            return parse_page_spec(spec, total)
        except ValueError as exc:
            log(f"invalid page spec: {exc}")
            hint = f"Invalid: {exc}\n"


def ask_password(parent: QWidget | None, title: str, *, confirm: bool) -> str | None:
    """Ask for a non-blank password, twice when ``confirm``. None when cancelled."""
    hint = ""
    while True:
        first, ok = QInputDialog.getText(parent, title, f"{hint}Password:", QLineEdit.EchoMode.Password)
        if not ok:
            return None
        if not first:
            hint = "The password cannot be blank.\n"
            continue
        if not confirm:
            return first
        again, ok = QInputDialog.getText(parent, title, "Type it again:", QLineEdit.EchoMode.Password)
        if not ok:
            return None
        if again == first:
            return first
        hint = "The two did not match.\n"


def ask_fields(parent: QWidget | None, title: str, fields: dict[str, str]) -> dict[str, str] | None:
    """One line edit per field, prefilled. Returns the edited values, or None when cancelled."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    form = QFormLayout(dialog)
    edits = {}
    for label, value in fields.items():
        edits[label] = QLineEdit(value)
        form.addRow(f"{label}:", edits[label])
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return {label: edit.text() for label, edit in edits.items()}


Presets = dict[str, str]  # colour name -> "#rrggbb"; a field of this type gets swatches plus a colour picker


def _swatch(hex_color: str) -> QIcon:
    pix = QPixmap(14, 14)
    pix.fill(QColor(hex_color))
    return QIcon(pix)


def _color_combo(presets: Presets) -> QComboBox:
    """Preset swatches, then "Pick colour..." which opens the system colour dialog and adds the result."""
    combo = QComboBox()
    for name, hex_color in presets.items():
        combo.addItem(_swatch(hex_color), name, hex_color)
    combo.addItem("Pick colour...", None)
    previous = [0]

    def chosen(index: int) -> None:
        if combo.itemData(index) is not None:
            previous[0] = index
            return
        color = QColorDialog.getColor(QColor(combo.itemData(previous[0])), combo, "Pick colour")
        if color.isValid():
            combo.insertItem(index, _swatch(color.name()), f"Custom ({color.name()})", color.name())
            previous[0] = index
        combo.setCurrentIndex(previous[0])

    combo.activated.connect(chosen)
    return combo


def ask_options(
    parent: QWidget | None, title: str, fields: dict[str, bool | str | list[str] | Presets],
) -> dict[str, bool | str] | None:
    """One row per field: a checkbox for a bool, a line edit for a str, a drop-down for a list (first item
    preselected), swatches plus a colour picker for a ``Presets`` dict. Returns checked / typed text / chosen text /
    chosen "#rrggbb"; None when cancelled."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    form = QFormLayout(dialog)
    widgets: dict[str, QCheckBox | QComboBox | QLineEdit] = {}
    for label, value in fields.items():
        if isinstance(value, str):
            widgets[label] = QLineEdit(value)
            form.addRow(f"{label}:", widgets[label])
            continue
        if isinstance(value, bool):
            box = QCheckBox()
            box.setChecked(value)
            widgets[label] = box
            form.addRow(label, box)
            continue
        if isinstance(value, dict):
            combo = _color_combo(value)
        else:
            combo = QComboBox()
            combo.addItems(value)
        widgets[label] = combo
        form.addRow(f"{label}:", combo)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    def value(w: QCheckBox | QComboBox | QLineEdit) -> bool | str:
        if isinstance(w, QCheckBox):
            return w.isChecked()
        if isinstance(w, QLineEdit):
            return w.text()
        return w.currentData() or w.currentText()

    return {label: value(w) for label, w in widgets.items()}
