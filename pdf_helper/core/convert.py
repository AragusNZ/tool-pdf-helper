"""Any supported file -> PDF. Dispatches on extension."""

from pathlib import Path

import pymupdf

from pdf_helper.core.office import OFFICE_EXTS, office_to_pdf
from pdf_helper.core.paths import fresh

# Raster formats: these are the ones a page size can be chosen for.
IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".pnm", ".pgm", ".ppm"})
# Everything else MuPDF opens directly and can re-save as PDF; these carry their own page layout.
MUPDF_EXTS = IMAGE_EXTS | frozenset({".txt", ".xps", ".epub", ".mobi", ".fb2", ".cbz", ".svg"})
PDF_EXT = ".pdf"

IMAGE_SIZE = "Image size"
AUTO = "Auto (A4)"
MATCH = "Match the image"
# Page sizes offered for images. Screen sizes are one point per pixel.
PAGE_SIZES: dict[str, tuple[float, float] | None] = {
    AUTO: pymupdf.paper_size("a4"),
    IMAGE_SIZE: None,
    "A4": pymupdf.paper_size("a4"),
    "A3": pymupdf.paper_size("a3"),
    "A5": pymupdf.paper_size("a5"),
    "Letter": pymupdf.paper_size("letter"),
    "Legal": pymupdf.paper_size("legal"),
    "HD 1920x1080": (1920, 1080),
    "4K 3840x2160": (3840, 2160),
}
# Asked only for a fixed size; AUTO and IMAGE_SIZE settle orientation on their own.
ORIENTATIONS = (MATCH, "Portrait", "Landscape")


class UnsupportedFile(ValueError):
    pass


def supported_extensions() -> frozenset[str]:
    return frozenset({PDF_EXT}) | MUPDF_EXTS | OFFICE_EXTS


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in supported_extensions()


def _image_to_pdf(src: Path, out: Path, size: tuple[float, float], orientation: str) -> None:
    """One page per frame at ``size``, in ``orientation``, the picture scaled to fit."""
    short, long = sorted(size)
    landscape = {"Portrait": False, "Landscape": True}
    with pymupdf.open(src) as img, pymupdf.open() as doc:
        for frame in img:
            pix = frame.get_pixmap()
            wide = landscape.get(orientation, pix.width > pix.height)
            width, height = (long, short) if wide else (short, long)
            page = doc.new_page(width=width, height=height)
            page.insert_image(page.rect, pixmap=pix, keep_proportion=True)
        doc.save(out)


def to_pdf(src: Path, out_dir: Path, log=print, page_size: str = IMAGE_SIZE, orientation: str = MATCH) -> Path:
    """Return a PDF path for ``src``. PDFs are returned as-is; others are written to ``out_dir``.

    ``page_size`` is a key of ``PAGE_SIZES`` and ``orientation`` one of ``ORIENTATIONS``; both
    apply to raster images only. The default puts each image on a page its own size; any other
    choice scales it onto that page, turned to match the image unless an orientation is forced.
    """
    ext = src.suffix.lower()
    if ext == PDF_EXT:
        return src
    out = fresh(out_dir / f"{src.stem}.pdf")
    size = PAGE_SIZES.get(page_size)
    if ext in OFFICE_EXTS:
        office_to_pdf(src, out, log=log)
    elif ext in IMAGE_EXTS and size is not None:
        _image_to_pdf(src, out, size, orientation)
    elif ext in MUPDF_EXTS:
        with pymupdf.open(src) as doc:
            pdf_bytes = doc.convert_to_pdf()
        out.write_bytes(pdf_bytes)
    else:
        raise UnsupportedFile(f"don't know how to convert {src.name}")
    return out
