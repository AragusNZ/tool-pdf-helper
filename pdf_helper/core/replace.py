"""Find-and-replace text in a PDF via redaction: each hit is redacted and the new text drawn in its place."""

from pathlib import Path

import pymupdf

from pdf_helper.core.pdf import open_pdf


def replace_text(src: Path, old: str, new: str, out: Path, *, case_sensitive: bool = False) -> int:
    """Replace every occurrence of ``old`` with ``new``. Returns the number of replacements.

    Keeps the original size and colour; the font falls back to Helvetica because redaction
    can only reinsert base-14 fonts. Longer replacements are shrunk to fit the original box.

    The replacement is drawn after the redactions rather than handed to the redaction annotation:
    PyMuPDF's own reinsertion wraps the text inside the old box and drops it below about 4 pt.
    """
    count = 0
    with open_pdf(src) as doc:
        for page in doc:
            hits: list[tuple[pymupdf.Rect, float, tuple, float]] = []
            for rect in page.search_for(old):  # search_for is case-insensitive
                if case_sensitive and page.get_textbox(rect).strip() != old:
                    continue
                spans = [
                    s for b in page.get_text("dict", clip=rect)["blocks"] for line in b["lines"] for s in line["spans"]
                ]
                size = spans[0]["size"] if spans else 11.0
                rgb = spans[0]["color"] if spans else 0
                color = tuple(((rgb >> shift) & 255) / 255 for shift in (16, 8, 0))
                baseline = spans[0]["origin"][1] if spans else rect.y1 - size * 0.2
                width = pymupdf.get_text_length(new, fontname="helv", fontsize=size)
                if width > rect.width:
                    size *= rect.width / width  # shrink rather than wrap or overrun the neighbours
                hits.append((rect, size, color, baseline))
                page.add_redact_annot(rect, fill=False)
                count += 1
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
            for rect, size, color, baseline in hits:
                if new:
                    page.insert_text((rect.x0, baseline), new, fontname="helv", fontsize=size, color=color)
        doc.save(out)
    return count
