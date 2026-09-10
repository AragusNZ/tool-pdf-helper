import os
from pathlib import Path

import pymupdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def make_pdf(tmp_path: Path):
    def _make(name: str, pages: int) -> Path:
        out = tmp_path / name
        with pymupdf.open() as doc:
            for i in range(pages):
                page = doc.new_page()
                page.insert_text((72, 72), f"{name} page {i + 1}")
            doc.save(out)
        return out

    return _make


@pytest.fixture
def make_png(tmp_path: Path):
    def _make(name: str = "pic.png", size: int = 30) -> Path:
        out = tmp_path / name
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, size, size), False)
        pix.clear_with(120)
        pix.save(out)
        return out

    return _make


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def log():
    """Collecting logger: call it, then inspect ``log.lines``."""
    lines: list[str] = []

    def _log(msg: str) -> None:
        lines.append(msg)

    _log.lines = lines  # type: ignore[attr-defined]
    return _log
