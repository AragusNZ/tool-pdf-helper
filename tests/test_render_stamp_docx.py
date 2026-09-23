import zipfile
from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.render import render_page_png, render_pages
from pdf_helper.core.replace import replace_text
from pdf_helper.core.stamp import add_image, add_text, fonts, image_size, watermark


def test_render_pages(make_pdf, tmp_path: Path):
    files = render_pages(make_pdf("r.pdf", 2), tmp_path / "png", dpi=72)
    assert [f.name for f in files] == ["r-p001.png", "r-p002.png"]
    assert all(f.stat().st_size > 0 for f in files)


def test_watermark_text_present(make_pdf, tmp_path: Path):
    out = tmp_path / "w.pdf"
    watermark(make_pdf("w0.pdf", 2), "DRAFT", out)
    with pymupdf.open(out) as doc:
        assert all("DRAFT" in p.get_text() for p in doc)


@pytest.mark.parametrize("case_sensitive, expected_n, lower_survives", [(False, 3, False), (True, 2, True)])
def test_replace_text(tmp_path: Path, case_sensitive, expected_n, lower_survives):
    src = tmp_path / "src.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), "Price 100 NZD total, nzd lower")
        page.insert_text((72, 100), "Amount in NZD", fontsize=20, color=(1, 0, 0))
        doc.save(src)
    out = tmp_path / "out.pdf"
    assert replace_text(src, "NZD", "Euro", out, case_sensitive=case_sensitive) == expected_n
    with pymupdf.open(out) as doc:
        text = doc[0].get_text()
        spans = [s for b in doc[0].get_text("dict")["blocks"] for l in b["lines"] for s in l["spans"]]
    assert "NZD" not in text and text.count("Euro") == expected_n
    assert all(w in text for w in ("Price 100", "total,", "lower", "Amount in"))
    assert ("nzd" in text) is lower_survives
    big = [s for s in spans if s["text"] == "Euro" and s["size"] > 15]  # shrunk from 20 to fit "Euro" in the "NZD" box
    assert big and big[0]["color"] == 0xFF0000


def test_to_docx(make_pdf, tmp_path: Path):
    pytest.importorskip("pdf2docx")
    from pdf_helper.core.docx import to_docx

    out = tmp_path / "d.docx"
    to_docx(make_pdf("d.pdf", 1), out)
    assert "word/document.xml" in zipfile.ZipFile(out).namelist()


def test_render_page_png(make_pdf):
    png, width, height = render_page_png(make_pdf("p.pdf", 2), 1, max_px=200)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    with pymupdf.open(make_pdf("p.pdf", 2)) as doc:
        assert (width, height) == (doc[1].rect.width, doc[1].rect.height)


def test_fonts_has_base14_and_extras():
    table = fonts()
    assert table["helv"] == "Helvetica" and "symb" not in table
    pytest.importorskip("pymupdf_fonts")
    assert table["figo"] == "FiraGO Regular"


def test_add_text_one_page_font_and_colour(make_pdf, tmp_path: Path):
    pytest.importorskip("pymupdf_fonts")
    out = tmp_path / "t.pdf"
    add_text(make_pdf("a.pdf", 3), out, "PAID", (100, 200), [1], fontname="figo", size=20, color=(1, 0, 0))
    with pymupdf.open(out) as doc:
        spans = [s for b in doc[1].get_text("dict")["blocks"] for l in b["lines"] for s in l["spans"]]
        placed = [s for s in spans if s["text"] == "PAID"]
        assert placed and placed[0]["color"] == 0xFF0000 and "Fira" in placed[0]["font"]
        assert abs(placed[0]["bbox"][0] - 100) < 2 and abs(placed[0]["bbox"][1] - 200) < 6
        assert "PAID" not in doc[0].get_text() and "PAID" not in doc[2].get_text()


def test_add_text_all_pages_and_rotated(tmp_path: Path):
    src = tmp_path / "rot.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=400, height=600)
        doc.new_page(width=400, height=600).set_rotation(90)
        doc.save(src)
    out = tmp_path / "rot-text.pdf"
    add_text(src, out, "HERE", (120, 60), None, size=14)
    with pymupdf.open(out) as doc:
        for page in doc:
            words = [w for w in page.get_text("words") if w[4] == "HERE"]
            assert words and abs(words[0][0] - 120) < 2 and abs(words[0][1] - 60) < 6


def test_add_text_rejects_bad_placement(make_pdf, tmp_path: Path):
    src = make_pdf("a.pdf", 1)
    with pytest.raises(ValueError, match="outside page 1"):
        add_text(src, tmp_path / "x.pdf", "hi", (9000, 9000), None)
    with pytest.raises(ValueError, match="does not fit"):
        add_text(src, tmp_path / "x.pdf", "far too long for the corner", (400, 780), None, size=40)


def test_add_image_rect_and_pages(make_pdf, make_png, tmp_path: Path):
    out = tmp_path / "i.pdf"
    add_image(make_pdf("a.pdf", 2), out, make_png("pic.png", 30), (100, 100, 160, 160), [0])
    with pymupdf.open(out) as doc:
        xref = doc[0].get_images()[0][0]
        assert doc[0].get_image_rects(xref)[0] == pymupdf.Rect(100, 100, 160, 160)
        assert not doc[1].get_images()


def test_add_image_rejects_empty_rect(make_pdf, make_png, tmp_path: Path):
    with pytest.raises(ValueError, match="empty"):
        add_image(make_pdf("a.pdf", 1), tmp_path / "x.pdf", make_png(), (10, 10, 10, 10), None)


def test_image_size(make_png):
    assert image_size(make_png("s.png", 24)) == (24, 24)
