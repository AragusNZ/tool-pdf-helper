"""PDF operations backed by PyMuPDF."""

from pathlib import Path

import pymupdf


def open_pdf(src: Path) -> pymupdf.Document:
    """Open a PDF for processing. Refuses password-protected files with a clear message."""
    doc = pymupdf.open(src)
    if doc.needs_pass:
        doc.close()
        raise ValueError(f"{src.name} is password-protected")
    return doc


def page_count(src: Path) -> int:
    with open_pdf(src) as doc:
        return doc.page_count


def merge(srcs: list[Path], out: Path) -> None:
    """Concatenate PDFs in the given order into ``out``."""
    with pymupdf.open() as merged:
        for src in srcs:
            with open_pdf(src) as doc:
                merged.insert_pdf(doc)
        merged.save(out)


def select_pages(src: Path, pages: list[int], out: Path) -> None:
    """Write a new PDF containing only ``pages`` (0-based, in the order given)."""
    with open_pdf(src) as doc:
        doc.select(pages)
        doc.save(out)


def split(src: Path, every: int, out_dir: Path) -> list[Path]:
    """Write chunks of ``every`` pages as <stem>-partNN.pdf."""
    if every < 1:
        raise ValueError("pages per file must be >= 1")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with open_pdf(src) as doc:
        total = doc.page_count
        for n, start in enumerate(range(0, total, every), start=1):
            out = out_dir / f"{src.stem}-part{n:02d}.pdf"
            with pymupdf.open() as part:
                part.insert_pdf(doc, from_page=start, to_page=min(start + every, total) - 1)
                part.save(out)
            written.append(out)
    return written


def rotate(src: Path, degrees: int, pages: list[int] | None, out: Path) -> None:
    """Rotate ``pages`` (0-based; None = all) clockwise by ``degrees`` (multiple of 90)."""
    with open_pdf(src) as doc:
        targets = range(doc.page_count) if pages is None else pages
        for i in targets:
            page = doc[i]
            page.set_rotation((page.rotation + degrees) % 360)
        doc.save(out)


def compress(src: Path, out: Path, *, dpi: int = 150, quality: int = 75) -> None:
    """Downsample images, subset fonts, garbage-collect and deflate."""
    with open_pdf(src) as doc:
        doc.rewrite_images(dpi_threshold=dpi + 1, dpi_target=dpi, quality=quality)
        doc.subset_fonts()
        doc.save(out, garbage=4, deflate=True, clean=True)
