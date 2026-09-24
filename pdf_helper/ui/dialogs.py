from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QFileDialog, QInputDialog, QWidget

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
