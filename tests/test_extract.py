import shutil
import subprocess
from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.extract import extract_images, extract_tables, extract_text, find_text, write_rtf
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


def _table_pdf(tmp_path: Path, rows: list[list[str]]) -> Path:
    """A ruled grid, which is what find_tables looks for."""
    out = tmp_path / "table.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                cell = pymupdf.Rect(100 + c * 120, 100 + r * 24, 220 + c * 120, 124 + r * 24)
                page.draw_rect(cell, color=(0, 0, 0))
                if value:
                    page.insert_text((cell.x0 + 4, cell.y1 - 8), value, fontsize=11)
        page.insert_text((100, 400), "Bolt and bolt again")
        doc.save(out)
    return out


def test_extract_tables(tmp_path: Path):
    src = _table_pdf(tmp_path, [["Name", "Qty"], ["Bolt", "12"], ["Nut", ""]])
    written = extract_tables(src, tmp_path / "csv")
    assert [p.name for p in written] == ["p001-01.csv"]
    # utf-8-sig so Excel opens it without mangling accents; an empty cell comes out blank
    assert written[0].read_text(encoding="utf-8-sig").splitlines() == ["Name,Qty", "Bolt,12", "Nut,"]


def test_extract_tables_finds_none(make_pdf, tmp_path: Path):
    assert extract_tables(make_pdf("plain.pdf", 1), tmp_path / "csv") == []


def test_find_text(tmp_path: Path):
    src = _table_pdf(tmp_path, [["Bolt", "12"]])
    assert find_text(src, "Bolt") == [(1, 3)]  # the cell plus "Bolt and bolt"
    assert find_text(src, "Bolt", case_sensitive=True) == [(1, 2)]
    assert find_text(src, "sprocket") == []
