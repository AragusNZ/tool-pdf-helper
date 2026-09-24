"""PDF operations backed by PyMuPDF."""

import re
from pathlib import Path

import pymupdf

from pdf_helper.core.paths import fresh


def open_pdf(src: Path) -> pymupdf.Document:
    """Open a PDF for processing. Refuses password-protected files with a clear message."""
    doc = pymupdf.open(src)
    if doc.needs_pass:
        doc.close()
        raise ValueError(f"{src.name} is password-protected")
    return doc


def _not_source(out: Path, srcs: list[Path]) -> None:
    """Refuse to write over an input. PyMuPDF's own message for this is about incremental saves."""
    if any(out.resolve() == src.resolve() for src in srcs):
        raise ValueError(f"{out.name} is one of the input files - choose another name")


def page_count(src: Path) -> int:
    with open_pdf(src) as doc:
        return doc.page_count


def merge(srcs: list[Path], out: Path) -> None:
    """Concatenate PDFs in the given order into ``out``."""
    _not_source(out, srcs)
    with pymupdf.open() as merged:
        for src in srcs:
            with open_pdf(src) as doc:
                merged.insert_pdf(doc)
        merged.save(out)


def select_pages(src: Path, pages: list[int], out: Path) -> None:
    """Write a new PDF containing only ``pages`` (0-based, in the order given)."""
    _not_source(out, [src])
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
            out = fresh(out_dir / f"{src.stem}-part{n:02d}.pdf")
            with pymupdf.open() as part:
                part.insert_pdf(doc, from_page=start, to_page=min(start + every, total) - 1)
                part.save(out)
            written.append(out)
    return written


def rotate(src: Path, degrees: int, pages: list[int] | None, out: Path) -> None:
    """Rotate ``pages`` (0-based; None = all) clockwise by ``degrees`` (multiple of 90).

    A page named twice in the spec is rotated once: "1,1" means page 1, not two turns.
    """
    _not_source(out, [src])
    with open_pdf(src) as doc:
        targets = range(doc.page_count) if pages is None else dict.fromkeys(pages)
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


def grayscale(src: Path, out: Path) -> None:
    """Convert every colour in the document to its grey equivalent."""
    _not_source(out, [src])
    with open_pdf(src) as doc:
        doc.recolor(1)
        doc.save(out)


def _safe_stem(title: str) -> str:
    """A bookmark title reduced to something a filesystem accepts."""
    cleaned = re.sub(r'[\\/:*?"<>|]', "-", title).strip(" .")
    return cleaned[:60] or "untitled"


def split_by_toc(src: Path, out_dir: Path) -> list[Path]:
    """Write one PDF per top-level bookmark, covering the pages up to the next one."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with open_pdf(src) as doc:
        starts = [(entry[2] - 1, entry[1]) for entry in doc.get_toc() if entry[0] == 1 and entry[2] > 0]
        if not starts:
            raise ValueError(f"{src.name} has no top-level bookmarks")
        bounds = [s[0] for s in starts[1:]] + [doc.page_count]
        for n, ((start, title), end) in enumerate(zip(starts, bounds), start=1):
            if start >= end:
                continue  # two bookmarks on one page: the first covers nothing
            out = fresh(out_dir / f"{src.stem}-{n:02d} {_safe_stem(title)}.pdf")
            with pymupdf.open() as part:
                part.insert_pdf(doc, from_page=start, to_page=end - 1)
                part.save(out)
            written.append(out)
    return written
