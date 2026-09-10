import zipfile
from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.render import render_pages
from pdf_helper.core.replace import replace_text
from pdf_helper.core.stamp import watermark


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
