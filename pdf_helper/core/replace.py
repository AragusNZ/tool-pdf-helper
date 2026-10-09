"""Remove text from a PDF. Find-and-replace draws new text over each redacted hit; Redact leaves a box."""

from pathlib import Path

import pymupdf

from pdf_helper.core.pdf import _not_source, open_pdf
from pdf_helper.core.stamp import font_for


def replace_text(src: Path, old: str, new: str, out: Path, *, case_sensitive: bool = False) -> int:
    """Replace every occurrence of ``old`` with ``new``. Returns the number of replacements.

    Keeps the original size and colour; the font is Helvetica, or Noto Sans when the replacement
    has characters outside Latin-1. Longer replacements are shrunk to fit the original box.

    The replacement is drawn after the redactions rather than handed to the redaction annotation:
    PyMuPDF's own reinsertion wraps the text inside the old box and drops it below about 4 pt.
    """
    count = 0
    with open_pdf(src) as doc:
        for page in doc:
            hits: list[tuple[pymupdf.Rect, float, tuple, float, str]] = []
            for rect in page.search_for(old):  # search_for is case-insensitive
                if case_sensitive and page.get_textbox(rect).strip() not in old:  # a wrapped hit is one rect per line
                    continue
                spans = [
                    s for b in page.get_text("dict", clip=rect)["blocks"] for line in b.get("lines", ()) for s in line["spans"]
                ]
                size = spans[0]["size"] if spans else 11.0
                rgb = spans[0]["color"] if spans else 0
                color = tuple(((rgb >> shift) & 255) / 255 for shift in (16, 8, 0))
                baseline = spans[0]["origin"][1] if spans else rect.y1 - size * 0.2
                fontname = font_for(new)
                width = pymupdf.Font(fontname).text_length(new, fontsize=size)
                if width > rect.width:
                    size *= rect.width / width  # shrink rather than wrap or overrun the neighbours
                hits.append((rect, size, color, baseline, fontname))
                page.add_redact_annot(rect, fill=False)
                count += 1
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
            for rect, size, color, baseline, fontname in hits:
                if new:
                    page.insert_text((rect.x0, baseline), new, fontname=fontname, fontsize=size, color=color)
        doc.save(out)
    return count


def redact(
    src: Path,
    out: Path,
    boxes: dict[int, list[tuple[float, float, float, float]]] | None = None,
    needle: str = "",
    *,
    case_sensitive: bool = False,
    fill: tuple[float, float, float] = (0, 0, 0),
) -> int:
    """Black out ``boxes`` (page points, keyed by 0-based page) and every hit for ``needle``.

    Returns the number of areas removed. The text really goes: it is deleted from the page content,
    not covered over, and image pixels under a box go with it.
    """
    _not_source(out, [src])
    count = 0
    with open_pdf(src) as doc:
        for page in doc:
            # Boxes come from the preview in displayed space; redaction takes unrotated space.
            rects = [pymupdf.Rect(*r) * page.derotation_matrix for r in (boxes or {}).get(page.number, [])]
            if needle:
                for rect in page.search_for(needle):  # search_for is case-insensitive
                    if case_sensitive and page.get_textbox(rect).strip() not in needle:
                        continue
                    rects.append(rect)
            for rect in rects:
                page.add_redact_annot(rect, fill=fill)
                count += 1
            if rects:
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
        doc.save(out)
    return count
