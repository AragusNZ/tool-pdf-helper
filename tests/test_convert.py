from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.convert import UnsupportedFile, is_supported, to_pdf
from pdf_helper.core.office import find_libreoffice
from pdf_helper.core.pdf import page_count


def test_pdf_passthrough(make_pdf, tmp_path: Path):
    src = make_pdf("x.pdf", 1)
    assert to_pdf(src, tmp_path) == src


def test_image_to_pdf(tmp_path: Path):
    img = tmp_path / "pic.png"
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    pix.clear_with(200)
    pix.save(img)
    out = to_pdf(img, tmp_path)
    assert out.name == "pic.pdf" and page_count(out) == 1


def test_text_to_pdf(tmp_path: Path):
    txt = tmp_path / "note.txt"
    txt.write_text("hello\n")
    assert page_count(to_pdf(txt, tmp_path)) == 1


def test_unsupported(tmp_path: Path):
    bad = tmp_path / "x.zip"
    bad.write_bytes(b"")
    assert not is_supported(bad)
    with pytest.raises(UnsupportedFile):
        to_pdf(bad, tmp_path)


@pytest.mark.skipif(find_libreoffice() is None, reason="LibreOffice not installed")
def test_office_via_libreoffice(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PDF_HELPER_NO_COM", "1")
    # Simplest Office-family input LibreOffice accepts: RTF.
    rtf = tmp_path / "doc.rtf"
    rtf.write_text(r"{\rtf1\ansi Hello from RTF}")
    assert page_count(to_pdf(rtf, tmp_path, log=lambda _m: None)) == 1
