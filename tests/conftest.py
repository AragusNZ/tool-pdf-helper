import os
from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.paths import fresh

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


@pytest.fixture(autouse=True, scope="session")
def _settings_in_tmp(tmp_path_factory):
    """The app's QSettings land in a temp folder, not the operator's real HKCU / ~/.config store."""
    from PySide6.QtCore import QSettings

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("settings")))


def into(folder: Path, suffix: str, ext: str = ".pdf"):
    """The namer ``ask_output`` returns for a batch: ``folder`` / <stem><suffix><ext>, never overwriting."""
    return lambda src: fresh(folder / f"{src.stem}{suffix}{ext}")


def fake_ask_output(folder: Path | None):
    """Stand-in for ``ask_output``: the batch answer, into ``folder`` with the feature's own suffix; None = cancel."""
    return lambda parent, files, suffix, ext=".pdf": None if folder is None else into(folder, suffix, ext)


def ink_bbox(page: pymupdf.Page) -> tuple[int, int, int, int]:
    """(x0, x1, y0, y1) of the dark pixels on the rendered page, in displayed space - what a user sees."""
    pix = page.get_pixmap()
    dark = [(x, y) for y in range(pix.height) for x in range(pix.width) if sum(pix.pixel(x, y)) < 600]
    xs, ys = [p[0] for p in dark], [p[1] for p in dark]
    return min(xs), max(xs), min(ys), max(ys)


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
