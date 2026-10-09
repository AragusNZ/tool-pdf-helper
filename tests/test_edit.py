"""core.edit: several stamps chained onto one PDF, their one-line descriptions, and the edits file."""

from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.edit import EDITS_EXT, apply_edits, describe, load_edits, save_edits

TEXT = {"kind": "text", "text": "PAID", "pos": [72.0, 144.0], "pages": "", "font": "helv", "size": 30, "color": [1, 0, 0]}
NUMBERS = {"kind": "numbers", "fmt": "Page {n} of {total}", "position": "Top right"}
WATERMARK = {"kind": "watermark", "text": "DRAFT"}
REPLACE = {"kind": "replace", "old": "page", "new": "leaf", "case_sensitive": True}


def image(png: Path) -> dict:
    return {"kind": "image", "image": str(png), "rect": [50.0, 50.0, 110.0, 110.0], "pages": "1"}


def test_apply_edits_stacks_every_kind(make_pdf, make_png, tmp_path: Path):
    out = tmp_path / "out.pdf"
    notes = apply_edits(make_pdf("a.pdf", 2), out, [TEXT, image(make_png()), NUMBERS, WATERMARK, REPLACE])
    assert notes == ["2 replacement(s)"]
    with pymupdf.open(out) as doc:
        text = doc[1].get_text()
        assert "PAID" in text and "Page 2 of 2" in text and "DRAFT" in text and "leaf" in text and "page" not in text
        assert doc[0].get_images() and not doc[1].get_images()  # the image's page spec was honoured
    assert sorted(p.name for p in tmp_path.glob("*.pdf")) == ["a.pdf", "out.pdf"]  # no intermediates left behind


def test_apply_edits_refuses_nothing_to_do_and_the_source(make_pdf, tmp_path: Path):
    src = make_pdf("a.pdf", 1)
    with pytest.raises(ValueError, match="no edits"):
        apply_edits(src, tmp_path / "o.pdf", [])
    with pytest.raises(ValueError, match="one of the input files"):
        apply_edits(src, src, [WATERMARK])
    assert not (tmp_path / "o.pdf").exists()


def test_apply_edits_checks_the_page_spec_against_the_file(make_pdf, tmp_path: Path):
    with pytest.raises(ValueError, match="outside 1-1"):
        apply_edits(make_pdf("a.pdf", 1), tmp_path / "o.pdf", [{**TEXT, "pages": "4"}])
    assert not (tmp_path / "o.pdf").exists()


def test_apply_edits_unknown_kind(make_pdf, tmp_path: Path):
    with pytest.raises(KeyError):
        apply_edits(make_pdf("a.pdf", 1), tmp_path / "o.pdf", [{"kind": "fly"}])


def test_describe():
    assert describe(TEXT) == 'Text "PAID" on all pages'
    assert describe({**TEXT, "pages": "1-3"}) == 'Text "PAID" on pages 1-3'
    assert describe(image(Path("/x/logo.png"))) == "Image logo.png on page 1"
    assert describe({**image(Path("l.png")), "pages": "1,3"}) == "Image l.png on pages 1,3"
    assert describe(NUMBERS) == "Page numbers: Page 1 of 10, Top right"
    assert describe(WATERMARK) == 'Watermark "DRAFT"'
    assert describe(REPLACE) == 'Replace "page" with "leaf" (match case)'
    assert describe({**REPLACE, "case_sensitive": False}) == 'Replace "page" with "leaf"'


def test_edits_file_round_trip(tmp_path: Path):
    path = tmp_path / f"a{EDITS_EXT}"
    save_edits(path, [TEXT, REPLACE])
    assert load_edits(path) == [TEXT, REPLACE]


@pytest.mark.parametrize(
    "content", ['{"kind": "text"}', '[{"kind": "fly"}]', "[1]", '[{"kind": "watermark"}]', "not json", b"\xff\xfe"]
)
def test_edits_file_of_another_shape_is_refused(tmp_path: Path, content):
    path = tmp_path / f"x{EDITS_EXT}"
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    with pytest.raises(ValueError, match="not an edits file"):
        load_edits(path)
