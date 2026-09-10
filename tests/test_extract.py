import shutil
import subprocess
from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.extract import extract_images, extract_text, write_rtf
from pdf_helper.core.office import find_libreoffice


def _pixmap_png(tmp_path: Path) -> Path:
    img = tmp_path / "pic.png"
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 30, 30), False)
    pix.clear_with(120)
    pix.save(img)
    return img


def test_extract_images_dedupes(make_pdf, tmp_path: Path):
    src = make_pdf("img.pdf", 2)
    png = _pixmap_png(tmp_path)
    with pymupdf.open(src) as doc:
        xref = doc[0].insert_image(pymupdf.Rect(10, 10, 60, 60), filename=str(png))
        doc[1].insert_image(pymupdf.Rect(10, 10, 60, 60), xref=xref)  # same image reused
        doc.saveIncr()
    out = extract_images(src, tmp_path / "images")
    assert len(out) == 1 and out[0].name == "p001-01.png" and out[0].stat().st_size > 0


def test_extract_text_per_page(make_pdf):
    pages = extract_text(make_pdf("t.pdf", 3))
    assert len(pages) == 3 and "t.pdf page 2" in pages[1]


def test_write_rtf_escapes(tmp_path: Path):
    out = tmp_path / "x.rtf"
    write_rtf(["a{b}\\c é\r\nline2", "p2 😀"], out)
    text = out.read_text(encoding="ascii")
    assert text.startswith("{\\rtf1")
    assert "a\\{b\\}\\\\c \\u233?" in text
    assert "\\par" in text and "\\page" in text
    assert "\\u-10179?\\u-8704?" in text  # 😀 as surrogate pair


@pytest.mark.skipif(find_libreoffice() is None, reason="LibreOffice not installed")
def test_rtf_roundtrip_libreoffice(tmp_path: Path):
    out = tmp_path / "r.rtf"
    write_rtf(["hello é", "second"], out)
    subprocess.run([find_libreoffice(), "--headless", "--convert-to", "txt", "--outdir", str(tmp_path), str(out)],
                   check=True, capture_output=True, timeout=120)
    text = (tmp_path / "r.txt").read_text(encoding="utf-8", errors="replace")
    assert "hello é" in text and "second" in text
