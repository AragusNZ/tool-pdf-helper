"""Render PDF pages to raster images."""

from pathlib import Path

from pdf_helper.core.pdf import open_pdf


def render_pages(src: Path, out_dir: Path, dpi: int = 150, fmt: str = "png") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with open_pdf(src) as doc:
        for page in doc:
            out = out_dir / f"{src.stem}-p{page.number + 1:03d}.{fmt}"
            page.get_pixmap(dpi=dpi).save(out)
            written.append(out)
    return written
