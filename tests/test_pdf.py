from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.pdf import merge, page_count, rotate, select_pages


def test_merge_keeps_order(make_pdf, tmp_path: Path):
    a, b = make_pdf("a.pdf", 2), make_pdf("b.pdf", 3)
    out = tmp_path / "merged.pdf"
    merge([b, a], out)
    assert page_count(out) == 5
    with pymupdf.open(out) as doc:
        assert "b.pdf page 1" in doc[0].get_text()
        assert "a.pdf page 1" in doc[3].get_text()


def test_select_pages(make_pdf, tmp_path: Path):
    src = make_pdf("src.pdf", 5)
    out = tmp_path / "out.pdf"
    select_pages(src, [4, 0], out)
    with pymupdf.open(out) as doc:
        assert doc.page_count == 2
        assert "page 5" in doc[0].get_text()
        assert "page 1" in doc[1].get_text()


def test_open_pdf_rejects_password_protected(make_pdf, tmp_path: Path):
    from pdf_helper.core.pdf import open_pdf, page_count

    src = make_pdf("a.pdf", 1)
    locked = tmp_path / "locked.pdf"
    with pymupdf.open(src) as doc:
        doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="x")
    with pytest.raises(ValueError, match="locked.pdf is password-protected - use Unlock first"):
        open_pdf(locked)
    with pytest.raises(ValueError, match="password-protected"):
        page_count(locked)


def test_writing_over_an_input_is_refused(make_pdf, tmp_path: Path):
    """The old behaviour silently replaced the source with the merged file."""
    a, b = make_pdf("a.pdf", 2), make_pdf("b.pdf", 3)
    for call in (lambda: merge([a, b], a), lambda: select_pages(a, [0], a), lambda: rotate(a, 90, None, a)):
        with pytest.raises(ValueError, match="a.pdf is one of the input files"):
            call()
    assert page_count(a) == 2  # untouched


def test_writing_over_an_input_compares_resolved_paths(make_pdf, tmp_path: Path):
    a = make_pdf("a.pdf", 1)
    with pytest.raises(ValueError, match="one of the input files"):
        merge([a], tmp_path / "sub" / ".." / "a.pdf")
