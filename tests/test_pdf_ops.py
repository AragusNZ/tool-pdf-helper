from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.pdf import compress, grayscale, page_count, rotate, split, split_by_toc
from pdf_helper.core.replace import redact


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


def test_rotate_turns_a_repeated_page_once(make_pdf, tmp_path: Path):
    """A spec of "1,1" parses to [0, 0]; rotating twice would land the page on 180."""
    out = tmp_path / "r.pdf"
    rotate(make_pdf("r0.pdf", 2), 90, [0, 0], out)
    with pymupdf.open(out) as doc:
        assert [p.rotation for p in doc] == [90, 0]


def test_split_never_overwrites_an_earlier_run(make_pdf, tmp_path: Path):
    first = split(make_pdf("s.pdf", 2), 1, tmp_path)
    again = split(make_pdf("s.pdf", 2), 1, tmp_path)
    assert [p.name for p in first] == ["s-part01.pdf", "s-part02.pdf"]
    assert [p.name for p in again] == ["s-part01 (2).pdf", "s-part02 (2).pdf"]


def _bookmarked(tmp_path: Path, toc: list[list], pages: int = 6) -> Path:
    out = tmp_path / "book.pdf"
    with pymupdf.open() as doc:
        for i in range(pages):
            doc.new_page().insert_text((72, 72), f"page {i + 1}")
        doc.set_toc(toc)
        doc.save(out)
    return out


def test_split_by_toc(tmp_path: Path):
    src = _bookmarked(tmp_path, [[1, "One", 1], [1, "Two/Three", 3], [2, "sub", 4], [1, "Last", 5]])
    parts = split_by_toc(src, tmp_path / "out")
    # level-2 entries are not split points, and a title keeps its characters bar the illegal ones
    assert [p.name for p in parts] == ["book-01 One.pdf", "book-02 Two-Three.pdf", "book-03 Last.pdf"]
    assert [page_count(p) for p in parts] == [2, 2, 2]


def test_split_by_toc_skips_an_empty_chapter(tmp_path: Path):
    """Two bookmarks on one page: the first covers no pages and is not written."""
    src = _bookmarked(tmp_path, [[1, "Cover", 1], [1, "Body", 1]], pages=2)
    parts = split_by_toc(src, tmp_path / "out")
    assert [p.name for p in parts] == ["book-02 Body.pdf"] and page_count(parts[0]) == 2


def test_split_by_toc_without_bookmarks(make_pdf, tmp_path: Path):
    with pytest.raises(ValueError, match="no top-level bookmarks"):
        split_by_toc(make_pdf("plain.pdf", 2), tmp_path / "out")


def test_split_by_toc_names_an_untitled_chapter(tmp_path: Path):
    src = _bookmarked(tmp_path, [[1, " . ", 1]], pages=1)
    assert split_by_toc(src, tmp_path / "out")[0].name == "book-01 untitled.pdf"


def test_grayscale(tmp_path: Path):
    src, out = tmp_path / "c.pdf", tmp_path / "g.pdf"
    with pymupdf.open() as doc:
        doc.new_page().draw_rect(pymupdf.Rect(50, 50, 200, 200), color=(1, 0, 0), fill=(1, 0, 0))
        doc.save(src)
    grayscale(src, out)
    with pymupdf.open(out) as doc:
        red, green, blue = doc[0].get_pixmap().pixel(100, 100)
    assert red == green == blue and red not in (0, 255)


def test_grayscale_refuses_its_own_source(make_pdf):
    src = make_pdf("a.pdf", 1)
    with pytest.raises(ValueError, match="one of the input files"):
        grayscale(src, src)


# --- redaction --------------------------------------------------------------
def test_redact_removes_boxes_and_matches(tmp_path: Path):
    src, out = tmp_path / "s.pdf", tmp_path / "r.pdf"
    with pymupdf.open() as doc:
        first = doc.new_page()
        first.insert_text((72, 72), "secret code")
        first.insert_text((72, 200), "keep this")
        doc.new_page().insert_text((72, 72), "secret again")
        doc.save(src)
    assert redact(src, out, {0: [(60, 60, 200, 80)]}, "secret") == 3
    with pymupdf.open(out) as doc:
        assert doc[0].get_text().split() == ["keep", "this"] and doc[1].get_text().split() == ["again"]


def test_redact_honours_case_and_leaves_untouched_pages_alone(tmp_path: Path):
    src, out = tmp_path / "s.pdf", tmp_path / "r.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "Secret and secret")
        doc.new_page().insert_text((72, 72), "nothing here")
        doc.save(src)
    assert redact(src, out, None, "Secret", case_sensitive=True) == 1
    with pymupdf.open(out) as doc:
        assert doc[0].get_text().split() == ["and", "secret"] and doc[1].get_text().strip() == "nothing here"


def test_redact_refuses_its_own_source(make_pdf):
    src = make_pdf("a.pdf", 1)
    with pytest.raises(ValueError, match="one of the input files"):
        redact(src, src, None, "x")


def test_split_by_toc_sorts_a_jumbled_contents(tmp_path: Path):
    """A contents list naming a later page first must not swallow the chapter before it."""
    src = _bookmarked(tmp_path, [[1, "Later", 4], [1, "Earlier", 2]])
    parts = split_by_toc(src, tmp_path / "out")
    assert [p.name for p in parts] == ["book-01 Earlier.pdf", "book-02 Later.pdf"]
    assert [page_count(p) for p in parts] == [2, 3]  # pages 2-3 and 4-6; page 1 is before any bookmark


def test_split_by_toc_strips_control_characters(tmp_path: Path):
    src = _bookmarked(tmp_path, [[1, "Two\nlines", 1]], pages=1)
    assert split_by_toc(src, tmp_path / "out")[0].name == "book-01 Two-lines.pdf"
