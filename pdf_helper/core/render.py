"""Render PDF pages to raster images."""

from collections.abc import Callable
from pathlib import Path

import pymupdf

from pdf_helper.core.paths import fresh
from pdf_helper.core.pdf import open_pdf


def render_pages(src: Path, out_dir: Path, dpi: int = 150, fmt: str = "png") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with open_pdf(src) as doc:
        for page in doc:
            out = fresh(out_dir / f"{src.stem}-p{page.number + 1:03d}.{fmt}")
            page.get_pixmap(dpi=dpi).save(out)
            written.append(out)
    return written


def render_page_png(
    src: Path, page_no: int, max_px: int = 700, stamp: Callable[[pymupdf.Page], None] | None = None
) -> tuple[bytes, float, float]:
    """PNG bytes of one 0-based page scaled to fit ``max_px``, plus page width and height in points.

    The pixmap and ``page.rect`` share the displayed (rotation-applied) coordinate space, so a click
    maps back by one divide. The insertion and redaction functions in core derotate on the way in.
    ``stamp`` is drawn on the page first and shown, never saved: the placement dialogs preview with it.
    """
    with open_pdf(src) as doc:
        page = doc[page_no]
        if stamp is not None:
            stamp(page)
        scale = max_px / max(page.rect.width, page.rect.height)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
        return pixmap.tobytes("png"), page.rect.width, page.rect.height
