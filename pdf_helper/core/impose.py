"""Lay source pages out on new sheets: N-up for printing, or one page per sheet to resize."""

from pathlib import Path

import pymupdf

from pdf_helper.core.convert import MATCH
from pdf_helper.core.pdf import _not_source, open_pdf


def _sheet(
    size: tuple[float, float], cols: int, rows: int, source: pymupdf.Rect, orientation: str
) -> tuple[float, float]:
    """Sheet width and height: the forced orientation, or the one whose cells fit the source best."""
    short, long = sorted(size)
    forced = {"Portrait": (short, long), "Landscape": (long, short)}
    if orientation in forced:
        return forced[orientation]
    wanted = source.width / source.height

    def mismatch(wh: tuple[float, float]) -> float:
        cell = (wh[0] / cols) / (wh[1] / rows)
        return max(cell / wanted, wanted / cell)

    return min(((short, long), (long, short)), key=mismatch)


def impose(
    src: Path,
    out: Path,
    *,
    cols: int = 1,
    rows: int = 1,
    size: tuple[float, float] = (595, 842),
    orientation: str = MATCH,
) -> None:
    """Place ``cols * rows`` source pages on each sheet of ``size``, scaled to fit and centred.

    ``cols=rows=1`` is a plain resize. The sheet keeps ``orientation``, or turns to suit the first
    page of each sheet when that is ``MATCH``. Annotations and links are not carried over -
    ``show_pdf_page`` copies page content only.
    """
    _not_source(out, [src])
    per = cols * rows
    with open_pdf(src) as doc, pymupdf.open() as book:
        for start in range(0, doc.page_count, per):
            width, height = _sheet(size, cols, rows, doc[start].rect, orientation)
            sheet = book.new_page(width=width, height=height)
            for i in range(start, min(start + per, doc.page_count)):
                col, row = (i - start) % cols, (i - start) // cols
                cell = pymupdf.Rect(
                    col * width / cols, row * height / rows, (col + 1) * width / cols, (row + 1) * height / rows
                )
                sheet.show_pdf_page(cell, doc, i, keep_proportion=True)
        book.save(out)
