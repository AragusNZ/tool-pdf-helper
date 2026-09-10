from pathlib import Path

import pymupdf

from pdf_helper.core.pdf import compress, page_count, rotate, split


def test_split(make_pdf, tmp_path: Path):
    parts = split(make_pdf("s.pdf", 5), 2, tmp_path / "parts")
    assert [p.name for p in parts] == ["s-part01.pdf", "s-part02.pdf", "s-part03.pdf"]
    assert [page_count(p) for p in parts] == [2, 2, 1]


def test_rotate_some_pages(make_pdf, tmp_path: Path):
    out = tmp_path / "r.pdf"
    rotate(make_pdf("r0.pdf", 3), 90, [0, 2], out)
    with pymupdf.open(out) as doc:
        assert [p.rotation for p in doc] == [90, 0, 90]


def test_rotate_all(make_pdf, tmp_path: Path):
    out = tmp_path / "r.pdf"
    rotate(make_pdf("r0.pdf", 2), 180, None, out)
    with pymupdf.open(out) as doc:
        assert [p.rotation for p in doc] == [180, 180]


def test_compress_keeps_pages(make_pdf, tmp_path: Path):
    out = tmp_path / "c.pdf"
    compress(make_pdf("c0.pdf", 3), out, dpi=100, quality=60)
    assert page_count(out) == 3


def test_split_rejects_zero(make_pdf, tmp_path: Path):
    import pytest

    with pytest.raises(ValueError):
        split(make_pdf("s.pdf", 1), 0, tmp_path)
