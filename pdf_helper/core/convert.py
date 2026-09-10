"""Any supported file -> PDF. Dispatches on extension."""

from pathlib import Path

import pymupdf

from pdf_helper.core.office import OFFICE_EXTS, office_to_pdf

# Formats MuPDF opens directly and can re-save as PDF.
MUPDF_EXTS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".pnm", ".pgm", ".ppm",
     ".txt", ".xps", ".epub", ".mobi", ".fb2", ".cbz", ".svg"}
)
PDF_EXT = ".pdf"


class UnsupportedFile(ValueError):
    pass


def supported_extensions() -> frozenset[str]:
    return frozenset({PDF_EXT}) | MUPDF_EXTS | OFFICE_EXTS


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in supported_extensions()


def to_pdf(src: Path, out_dir: Path, log=print) -> Path:
    """Return a PDF path for ``src``. PDFs are returned as-is; others are written to ``out_dir``."""
    ext = src.suffix.lower()
    if ext == PDF_EXT:
        return src
    out = out_dir / f"{src.stem}.pdf"
    if ext in OFFICE_EXTS:
        office_to_pdf(src, out, log=log)
    elif ext in MUPDF_EXTS:
        with pymupdf.open(src) as doc:
            pdf_bytes = doc.convert_to_pdf()
        out.write_bytes(pdf_bytes)
    else:
        raise UnsupportedFile(f"don't know how to convert {src.name}")
    return out
