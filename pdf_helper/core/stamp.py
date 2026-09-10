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
