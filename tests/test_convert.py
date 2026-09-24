from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.convert import AUTO, PAGE_SIZES, UnsupportedFile, is_supported, to_pdf
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


def _png(path: Path, width: int, height: int) -> Path:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pix.clear_with(180)
    pix.save(path)
    return path


def _page(pdf: Path) -> tuple[float, float]:
    with pymupdf.open(pdf) as doc:
        return round(doc[0].rect.width), round(doc[0].rect.height)


def test_image_page_defaults_to_the_image_size(tmp_path: Path):
    out = to_pdf(_png(tmp_path / "wide.png", 300, 100), tmp_path)
    assert _page(out) == (225, 75)  # 300x100 px at 96 dpi


def test_image_page_size_and_auto_orientation(tmp_path: Path):
    wide = _png(tmp_path / "wide.png", 300, 100)
    tall = _png(tmp_path / "tall.png", 100, 300)
    assert _page(to_pdf(wide, tmp_path, page_size="A4")) == (842, 595)
    assert _page(to_pdf(tall, tmp_path, page_size="A4")) == (595, 842)
    assert _page(to_pdf(wide, tmp_path, page_size=AUTO)) == (842, 595)
    assert _page(to_pdf(wide, tmp_path, page_size="HD 1920x1080")) == (1920, 1080)


def test_image_orientation_can_be_forced(tmp_path: Path):
    wide = _png(tmp_path / "wide.png", 300, 100)
    assert _page(to_pdf(wide, tmp_path, page_size="A4", orientation="Portrait")) == (595, 842)
    assert _page(to_pdf(wide, tmp_path, page_size="A4", orientation="Landscape")) == (842, 595)
    tall = _png(tmp_path / "tall.png", 100, 300)
    assert _page(to_pdf(tall, tmp_path, page_size="A4", orientation="Landscape")) == (842, 595)


def test_every_offered_page_size_converts(tmp_path: Path):
    img = _png(tmp_path / "pic.png", 200, 200)
    for name in PAGE_SIZES:
        out = to_pdf(img, tmp_path, page_size=name)
        with pymupdf.open(out) as doc:
            assert doc.page_count == 1 and len(doc[0].get_images()) == 1


def test_page_size_leaves_non_images_alone(tmp_path: Path):
    txt = tmp_path / "note.txt"
    txt.write_text("hello\n")
    assert _page(to_pdf(txt, tmp_path, page_size="A4")) == _page(to_pdf(txt, tmp_path))


def test_output_name_is_numbered_rather_than_overwritten(tmp_path: Path):
    img = _png(tmp_path / "pic.png", 20, 20)
    first, second = to_pdf(img, tmp_path), to_pdf(img, tmp_path)
    assert first.name == "pic.pdf" and second.name == "pic (2).pdf"


def test_multi_page_tiff_gets_a_page_per_frame(tmp_path: Path):
    cv2 = pytest.importorskip("cv2")  # ships with pdf2docx; the only writer here for multi-page TIFF
    numpy = pytest.importorskip("numpy")

    src = tmp_path / "multi.tif"
    frames = [numpy.full((40, 80, 3), shade, numpy.uint8) for shade in (60, 200)]
    assert cv2.imwritemulti(str(src), frames)
    for size in ("Image size", "A4"):
        with pymupdf.open(to_pdf(src, tmp_path, page_size=size)) as doc:
            assert doc.page_count == 2

