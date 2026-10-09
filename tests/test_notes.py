"""Footnote comments: numbering, notes pages, replies, options, links, bookmarks, Markdown."""

from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.notes import NotesOptions, footnote_comments


def _commented(path: Path, notes: dict[int, list[str]], pages: int = 3) -> Path:
    """``pages`` pages; page i (0-based) gets a highlight per comment in ``notes[i]``, top to bottom."""
    with pymupdf.open() as doc:
        for i in range(pages):
            page = doc.new_page()
            for k in range(4):
                page.insert_text((72, 100 + 40 * k), f"line {k} of page {i + 1}")
            for k, comment in enumerate(notes.get(i, [])):
                annot = page.add_highlight_annot(pymupdf.Rect(72, 90 + 40 * k, 200, 104 + 40 * k))
                annot.set_info(content=comment, title="Ann")
                annot.update()
        doc.save(path)
    return path


def test_numbers_run_through_the_file_and_only_commented_pages_get_notes(tmp_path: Path):
    src = _commented(tmp_path / "a.pdf", {0: ["one", "two"], 2: ["three"]})
    out = tmp_path / "out.pdf"
    assert footnote_comments(src, out) == 3
    with pymupdf.open(out) as doc:
        texts = [p.get_text() for p in doc]
        assert doc.page_count == 5  # 3 + a notes page after pages 1 and 3
        assert texts[1].startswith("Notes for page 1") and "1. one" in texts[1] and "2. two" in texts[1]
        assert "line 0 of page 2" in texts[2] and "Notes" not in texts[2]
        assert texts[4].startswith("Notes for page 3") and "3. three" in texts[4]
        assert "3" in texts[3] and len(list(doc[3].annots())) == 1  # marker stamped, highlight kept
        assert "Ann" not in texts[1]  # authors off by default


def test_links_and_bookmarks(tmp_path: Path):
    src = _commented(tmp_path / "a.pdf", {0: ["one"], 1: ["two"]}, pages=2)
    with pymupdf.open(src) as doc:
        doc.set_toc([[1, "Chapter", 2]])
        doc.save(src, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    out = tmp_path / "out.pdf"
    footnote_comments(src, out)
    with pymupdf.open(out) as doc:
        assert doc.get_toc() == [[1, "Chapter", 3], [1, "Notes for page 1", 2], [1, "Notes for page 2", 4]]
        (to_note,) = doc[0].get_links()
        (back,) = doc[1].get_links()
        assert to_note["page"] == 1 and back["page"] == 0 and to_note["from"].x0 > 500  # right margin
        assert doc[2].get_links()[0]["page"] == 3 and doc[3].get_links()[0]["page"] == 2


def test_quote_authors_and_bake(tmp_path: Path):
    src = _commented(tmp_path / "a.pdf", {0: ["why"]}, pages=1)
    out = tmp_path / "out.pdf"
    footnote_comments(src, out, NotesOptions(quote=True, authors=True, bake=True))
    with pymupdf.open(out) as doc:
        assert "“line 0 of page 1” — why — Ann" in doc[1].get_text()
        assert not list(doc[0].annots())


def test_long_notes_spill_onto_more_pages(tmp_path: Path):
    src = _commented(tmp_path / "a.pdf", {0: ["word " * 400] * 4}, pages=1)
    out = tmp_path / "out.pdf"
    footnote_comments(src, out)
    with pymupdf.open(out) as doc:
        assert doc.page_count > 2 and all("word" in p.get_text() for p in doc[1:])
        assert {link["page"] for link in doc[0].get_links()} == {1, 2}  # markers reach the overflow page too


def test_uncommented_highlights_listed_only_on_request(tmp_path: Path):
    src = _commented(tmp_path / "a.pdf", {0: ["  ", "said"]}, pages=1)
    assert footnote_comments(src, tmp_path / "a-out.pdf") == 1
    assert footnote_comments(src, tmp_path / "b-out.pdf", NotesOptions(uncommented=True)) == 2
    with pymupdf.open(tmp_path / "b-out.pdf") as doc:
        assert "1. “line 0 of page 1”\n2. said" in doc[1].get_text()


def test_shapes_and_sticky_notes_count_but_free_text_and_blanks_do_not(tmp_path: Path):
    src = tmp_path / "a.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.add_highlight_annot(pymupdf.Rect(72, 90, 200, 104)).set_info(content="  ")
        page.add_text_annot((300, 300), "sticky")
        page.add_rect_annot(pymupdf.Rect(50, 400, 150, 450)).set_info(content="boxed")
        page.add_freetext_annot(pymupdf.Rect(50, 500, 150, 520), "typed on the page")
        doc.save(src)
    assert footnote_comments(src, tmp_path / "out.pdf") == 2
    with pymupdf.open(tmp_path / "out.pdf") as doc:
        assert "1. sticky" in doc[1].get_text() and "2. boxed" in doc[1].get_text()


def test_replies_fold_under_their_parent(tmp_path: Path):
    src = tmp_path / "a.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 100), "some text here")
        parent = page.add_highlight_annot(pymupdf.Rect(72, 90, 200, 104))
        parent.set_info(content="root", title="Ann")
        reply = page.add_text_annot((72, 90), "I disagree")
        reply.set_info(title="Bob")
        reply.set_irt_xref(parent.xref)
        again = page.add_text_annot((72, 90), "fair")
        again.set_info(title="Ann")
        again.set_irt_xref(reply.xref)  # a reply to the reply still lands under the root
        doc.save(src)
    out = tmp_path / "out.pdf"
    md = tmp_path / "out.md"
    assert footnote_comments(src, out, md=md) == 1
    with pymupdf.open(out) as doc:
        text = doc[1].get_text()
        assert "1. root" in text and "↳ Bob: I disagree" in text and "↳ Ann: fair" in text
    assert md.read_text(encoding="utf-8") == (
        "# Notes for a.pdf\n\n## Page 1\n\n1. root\n    - ↳ Bob: I disagree\n    - ↳ Ann: fair\n"
    )


@pytest.mark.parametrize("placement, pages, heading", [("end", 3, "Page 1"), ("only", 1, "Page 1")])
def test_notes_at_the_end_or_alone(tmp_path: Path, placement, pages, heading):
    src = _commented(tmp_path / "a.pdf", {0: ["one"], 1: ["two"]}, pages=2)
    out = tmp_path / "out.pdf"
    footnote_comments(src, out, NotesOptions(placement=placement))
    with pymupdf.open(out) as doc:
        assert doc.page_count == pages
        last = doc[-1].get_text()
        assert last.startswith(heading) and "1. one" in last and "Page 2\n2. two" in last
        if placement == "end":
            assert doc.get_toc() == [[1, "Notes", 3]] and doc[0].get_links()[0]["page"] == 2
        else:
            assert not doc[-1].get_links()


@pytest.mark.parametrize("marker, check", [("left", lambda r: r.x0 < 20), ("inline", lambda r: 200 < r.x0 < 210)])
def test_marker_position(tmp_path: Path, marker, check):
    src = _commented(tmp_path / "a.pdf", {0: ["one"]}, pages=1)
    out = tmp_path / "out.pdf"
    footnote_comments(src, out, NotesOptions(marker=marker))
    with pymupdf.open(out) as doc:
        assert check(doc[0].get_links()[0]["from"])


def test_bad_option_and_no_comments_are_errors(make_pdf, tmp_path: Path):
    with pytest.raises(ValueError, match="no comments"):
        footnote_comments(make_pdf("a.pdf", 1), tmp_path / "out.pdf")
    with pytest.raises(ValueError, match="unknown placement"):
        footnote_comments(make_pdf("b.pdf", 1), tmp_path / "out.pdf", NotesOptions(placement="sideways"))
