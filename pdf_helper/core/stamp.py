"""Diagonal text watermark on every page."""

from pathlib import Path

import pymupdf

from pdf_helper.core.pdf import open_pdf


def watermark(src: Path, text: str, out: Path, *, opacity: float = 0.25, size: int = 48, angle: int = 45) -> None:
    with open_pdf(src) as doc:
        for page in doc:
            width = pymupdf.get_text_length(text, fontsize=size)
            center = (page.rect.tl + page.rect.br) / 2
            origin = pymupdf.Point(center.x - width / 2, center.y + size / 3)
            page.insert_text(
                origin,
                text,
                fontsize=size,
                color=(0.5, 0.5, 0.5),
                fill_opacity=opacity,
                morph=(center, pymupdf.Matrix(angle)),
                overlay=True,
            )
        doc.save(out)


MM = 72 / 25.4  # PDF points per millimetre

# Base-14 short codes PyMuPDF understands, minus the two symbol fonts (no usable alphabet).
BASE14 = ("helv", "hebo", "heit", "hebi", "tiro", "tibo", "tiit", "tibi", "cour", "cobo", "coit", "cobi")


def fonts() -> dict[str, str]:
    """{font code: display name}. The extras appear only when pymupdf-fonts is installed."""
    base = {code: pymupdf.Base14_fontdict[code] for code in BASE14}
    extra = {code: desc["name"] for code, desc in pymupdf.fitz_fontdescriptors.items()}
    return base | extra


def add_text(
    src: Path,
    out: Path,
    text: str,
    pos: tuple[float, float],
    pages: list[int] | None = None,
    *,
    fontname: str = "helv",
    size: float = 12,
    color: tuple[float, float, float] = (0, 0, 0),
) -> None:
    """Write ``text`` with its top-left corner at ``pos`` (page points) on ``pages`` (0-based; None = all).

    The text box runs from ``pos`` to the bottom-right of the page, so long text wraps.
    Coordinates are in the page's displayed space: a rotated page needs no correction.
    A page named twice in the spec is written once.
    """
    with open_pdf(src) as doc:
        for i in range(doc.page_count) if pages is None else dict.fromkeys(pages):
            page = doc[i]
            box = pymupdf.Rect(pos[0], pos[1], page.rect.x1, page.rect.y1)
            if box.is_empty or box.is_infinite:
                raise ValueError(f"position {pos} is outside page {i + 1}")
            if page.insert_textbox(box, text, fontname=fontname, fontsize=size, color=color) < 0:
                raise ValueError(f"text does not fit on page {i + 1} at that position and size")
        doc.save(out)


def add_image(src: Path, out: Path, image: Path, rect: tuple[float, float, float, float], pages: list[int] | None = None) -> None:
    """Place ``image`` inside ``rect`` (page points) on ``pages`` (0-based; None = all), aspect preserved."""
    target = pymupdf.Rect(*rect)
    if target.is_empty or target.is_infinite:
        raise ValueError(f"image rectangle {rect} is empty")
    with open_pdf(src) as doc:
        for i in range(doc.page_count) if pages is None else dict.fromkeys(pages):
            doc[i].insert_image(target, filename=str(image), keep_proportion=True)
        doc.save(out)


def image_size(image: Path) -> tuple[int, int]:
    """Pixel width and height of a raster image, for keeping its aspect ratio."""
    pix = pymupdf.Pixmap(str(image))
    return pix.width, pix.height
