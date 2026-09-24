import zipfile
from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.convert import PAGE_SIZES
from pdf_helper.core.impose import impose
from pdf_helper.core.render import render_page_png, render_pages
from pdf_helper.core.replace import replace_text
from pdf_helper.core.stamp import (
    NUMBER_FORMATS, NUMBER_POSITIONS, add_image, add_text, fonts, image_size, page_numbers, watermark,
)


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


def test_replace_text_shrinks_instead_of_wrapping(tmp_path: Path):
    """A replacement longer than the original used to wrap inside the old box: "eleph" / "ant"."""
    src = tmp_path / "src.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "one cat two")
        doc.save(src)
    out = tmp_path / "out.pdf"
    assert replace_text(src, "cat", "elephant", out) == 1
    with pymupdf.open(out) as doc:
        spans = [s for b in doc[0].get_text("dict")["blocks"] for l in b["lines"] for s in l["spans"]]
    words = [s["text"] for s in spans]
    assert "elephant" in words and "cat" not in "".join(words)
    assert [s["size"] for s in spans if s["text"] == "elephant"][0] < 11  # shrunk to fit the old box


def test_replace_text_with_nothing_deletes_it(tmp_path: Path):
    src = tmp_path / "src.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "one cat two")
        doc.save(src)
    out = tmp_path / "out.pdf"
    assert replace_text(src, "cat", "", out) == 1
    with pymupdf.open(out) as doc:
        assert "cat" not in doc[0].get_text()


def test_add_text_writes_a_repeated_page_once(make_pdf, tmp_path: Path):
    out = tmp_path / "t.pdf"
    add_text(make_pdf("a.pdf", 2), out, "HELLO", (72, 144), [0, 0])
    with pymupdf.open(out) as doc:
        spans = [s for b in doc[0].get_text("dict")["blocks"] for l in b["lines"] for s in l["spans"]]
    assert [s["text"] for s in spans].count("HELLO") == 1


def test_render_pages_never_overwrites_an_earlier_run(make_pdf, tmp_path: Path):
    src = make_pdf("r.pdf", 1)
    render_pages(src, tmp_path, dpi=72)
    again = render_pages(src, tmp_path, dpi=72)
    assert [f.name for f in again] == ["r-p001 (2).png"]



# --- page numbers -----------------------------------------------------------
def test_page_numbers_every_page(make_pdf, tmp_path: Path):
    out = tmp_path / "n.pdf"
    page_numbers(make_pdf("a.pdf", 3), out, fmt=NUMBER_FORMATS["1 of 10"])
    with pymupdf.open(out) as doc:
        assert [p.get_text().split("\n")[-2] for p in doc] == ["1 of 3", "2 of 3", "3 of 3"]


@pytest.mark.parametrize("position", NUMBER_POSITIONS)
def test_page_numbers_positions_stay_on_the_page(make_pdf, tmp_path: Path, position):
    out = tmp_path / f"{position}.pdf"
    page_numbers(make_pdf("a.pdf", 1), out, position=position)
    with pymupdf.open(out) as doc:
        rect = doc[0].rect
        hit = doc[0].search_for("1")[-1]  # the number, not the body text
    assert rect.contains(hit)
    assert (hit.y0 < rect.height / 2) is position.startswith("Top")
    if position.endswith("left"):
        assert hit.x0 < rect.width / 3
    elif position.endswith("right"):
        assert hit.x1 > rect.width * 2 / 3


# --- impose -----------------------------------------------------------------
def test_impose_two_up(make_pdf, tmp_path: Path):
    out = tmp_path / "2up.pdf"
    impose(make_pdf("a.pdf", 5), out, cols=2, rows=1, size=PAGE_SIZES["A4"])
    with pymupdf.open(out) as doc:
        assert doc.page_count == 3  # 5 pages, 2 to a sheet
        assert doc[0].rect.width > doc[0].rect.height  # portrait sources turn the sheet landscape
        assert "a.pdf page 1" in doc[0].get_text() and "a.pdf page 2" in doc[0].get_text()
        assert doc[2].get_text().count("page") == 1  # the last sheet is half empty


def test_impose_resizes_one_page_per_sheet(make_pdf, tmp_path: Path):
    out = tmp_path / "a5.pdf"
    impose(make_pdf("a.pdf", 2), out, size=PAGE_SIZES["A5"])
    with pymupdf.open(out) as doc:
        assert doc.page_count == 2
        assert (round(doc[0].rect.width), round(doc[0].rect.height)) == (420, 595)  # A5 portrait, matching the source


def test_impose_forces_orientation(make_pdf, tmp_path: Path):
    out = tmp_path / "land.pdf"
    impose(make_pdf("a.pdf", 1), out, size=PAGE_SIZES["A4"], orientation="Landscape")
    with pymupdf.open(out) as doc:
        assert doc[0].rect.width > doc[0].rect.height and "a.pdf page 1" in doc[0].get_text()


def test_impose_refuses_its_own_source(make_pdf):
    src = make_pdf("a.pdf", 1)
    with pytest.raises(ValueError, match="one of the input files"):
        impose(src, src)
