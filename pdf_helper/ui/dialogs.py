from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QWidget


def save_pdf_path(parent: QWidget | None, suggested: Path) -> Path | None:
    name, _ = QFileDialog.getSaveFileName(parent, "Save PDF", str(suggested), "PDF (*.pdf)")
    if not name:
        return None
    path = Path(name)
    return path if path.suffix.lower() == ".pdf" else path.with_suffix(".pdf")


def open_file_paths(parent: QWidget | None, exts: frozenset[str]) -> list[Path]:
    pattern = " ".join(f"*{e}" for e in sorted(exts))
    names, _ = QFileDialog.getOpenFileNames(parent, "Add files", "", f"Supported ({pattern});;All files (*)")
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
