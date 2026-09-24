from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QInputDialog, QLineEdit, QWidget,
)

from pdf_helper.core.pages import parse_page_spec


def save_pdf_path(parent: QWidget | None, suggested: Path) -> Path | None:
    name, _ = QFileDialog.getSaveFileName(parent, "Save PDF", str(suggested), "PDF (*.pdf)")
    if not name:
        return None
    path = Path(name)
    return path if path.suffix.lower() == ".pdf" else path.with_suffix(".pdf")


def open_file_paths(parent: QWidget | None, exts: frozenset[str], start: str = "") -> list[Path]:
    pattern = " ".join(f"*{e}" for e in sorted(exts))
    names, _ = QFileDialog.getOpenFileNames(parent, "Add files", start, f"Supported ({pattern});;All files (*)")
    return [Path(n) for n in names]


def ask_text(parent: QWidget | None, title: str, prompt: str) -> str | None:
    text, ok = QInputDialog.getText(parent, title, prompt)
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
