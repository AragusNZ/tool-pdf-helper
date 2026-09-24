"""Every feature: queue gating, prepare() with dialogs stubbed, run() output."""

from pathlib import Path

import pymupdf
import pytest

from pdf_helper.core.convert import AUTO, IMAGE_SIZE, MATCH
from pdf_helper.core.pdf import page_count
from pdf_helper.features import (
    FEATURES, add_image, add_text, compress, create_pdf, extract_content, extract_pages, merge, replace_text, rotate,
    split, to_docx, to_images, watermark,
)
from pdf_helper.features.base import FeatureContext


def test_registry_labels_unique():
    labels = [f.label for f in FEATURES]
    assert len(labels) == len(set(labels)) == 13


def test_enabled_for_gating(make_pdf, make_png, tmp_path: Path):
    pdf, pdf2, png = make_pdf("a.pdf", 1), make_pdf("b.pdf", 1), make_png()
    bad = tmp_path / "x.zip"
    bad.write_bytes(b"")
    assert create_pdf.FEATURE.enabled_for([png]) and not create_pdf.FEATURE.enabled_for([bad])
    assert not create_pdf.FEATURE.enabled_for([])
    assert merge.FEATURE.enabled_for([pdf, png]) and not merge.FEATURE.enabled_for([pdf])
    assert extract_pages.FEATURE.enabled_for([pdf]) and not extract_pages.FEATURE.enabled_for([pdf, pdf2])
    assert not extract_pages.FEATURE.enabled_for([png])
    assert rotate.FEATURE.enabled_for([pdf]) and not rotate.FEATURE.enabled_for([pdf, pdf2])
    assert split.FEATURE.enabled_for([pdf, pdf2])


# --- create_pdf -------------------------------------------------------------
def test_create_pdf_run(make_pdf, make_png, log):
    pdf, png = make_pdf("a.pdf", 1), make_png()
    create_pdf.FEATURE.run(FeatureContext([pdf, png], log), (IMAGE_SIZE, MATCH))
    assert png.with_suffix(".pdf").exists()
    assert log.lines[0].startswith("skip a.pdf") and "created" in log.lines[1]


# --- merge ------------------------------------------------------------------
def test_merge_prepare_and_run(make_pdf, make_png, tmp_path: Path, log, monkeypatch):
    pdf, png = make_pdf("a.pdf", 2), make_png()
    out = tmp_path / "m.pdf"
    monkeypatch.setattr(merge, "save_pdf_path", lambda parent, suggested: out)
    monkeypatch.setattr(create_pdf, "ask_choice", lambda *a: IMAGE_SIZE)
    ctx = FeatureContext([pdf, png], log)
    params = merge.FEATURE.prepare(ctx)
    assert params == (out, IMAGE_SIZE, MATCH)
    merge.FEATURE.run(ctx, params)
    assert page_count(out) == 3 and "merged 2 files" in log.lines[-1]


def test_merge_prepare_cancel(make_pdf, log, monkeypatch):
    monkeypatch.setattr(merge, "save_pdf_path", lambda parent, suggested: None)
    assert merge.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None


# --- extract_pages ----------------------------------------------------------
def test_extract_pages_prepare_retries_bad_spec(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf, out = make_pdf("a.pdf", 5), tmp_path / "e.pdf"
    answers = iter(["99", "2-3"])
    monkeypatch.setattr(extract_pages, "ask_text", lambda *a: next(answers))
    monkeypatch.setattr(extract_pages, "save_pdf_path", lambda parent, suggested: out)
    ctx = FeatureContext([pdf], log)
    params = extract_pages.FEATURE.prepare(ctx)
    assert params == ([1, 2], out) and "invalid page spec" in log.lines[0]
    extract_pages.FEATURE.run(ctx, params)
    assert page_count(out) == 2


@pytest.mark.parametrize("spec_answer, save_answer", [(None, "unused"), ("1", None)])
def test_extract_pages_prepare_cancel(make_pdf, tmp_path: Path, log, monkeypatch, spec_answer, save_answer):
    monkeypatch.setattr(extract_pages, "ask_text", lambda *a: spec_answer)
    monkeypatch.setattr(extract_pages, "save_pdf_path", lambda *a: save_answer)
    assert extract_pages.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None


# --- extract_content --------------------------------------------------------
def test_extract_content(make_pdf, make_png, tmp_path: Path, log, monkeypatch):
    pdf = make_pdf("a.pdf", 1)
    with pymupdf.open(pdf) as doc:
        doc[0].insert_image(pymupdf.Rect(10, 10, 60, 60), filename=str(make_png()))
        doc.saveIncr()
    monkeypatch.setattr(extract_content, "choose_directory", lambda *a: tmp_path)
    ctx = FeatureContext([pdf], log)
    base = extract_content.FEATURE.prepare(ctx)
    extract_content.FEATURE.run(ctx, base)
    assert (tmp_path / "a-content" / "images" / "p001-01.png").exists()
    assert (tmp_path / "a-content" / "a.rtf").exists() and "1 image(s)" in log.lines[0]


# --- split ------------------------------------------------------------------
def test_split_feature(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf = make_pdf("a.pdf", 3)
    monkeypatch.setattr(split, "ask_int", lambda *a: 2)
    monkeypatch.setattr(split, "choose_directory", lambda *a: tmp_path / "out")
    ctx = FeatureContext([pdf], log)
    params = split.FEATURE.prepare(ctx)
    split.FEATURE.run(ctx, params)
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["a-part01.pdf", "a-part02.pdf"]


def test_split_prepare_cancel(make_pdf, log, monkeypatch):
    monkeypatch.setattr(split, "ask_int", lambda *a: None)
    assert split.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None
    monkeypatch.setattr(split, "ask_int", lambda *a: 1)
    monkeypatch.setattr(split, "choose_directory", lambda *a: None)
    assert split.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None


# --- rotate -----------------------------------------------------------------
def test_rotate_feature_page_spec(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf, out = make_pdf("a.pdf", 3), tmp_path / "r.pdf"
    answers = iter(["bad", "2"])
    monkeypatch.setattr(rotate, "ask_choice", lambda *a: "90")
    monkeypatch.setattr(rotate, "ask_text", lambda *a: next(answers))
    monkeypatch.setattr(rotate, "save_pdf_path", lambda *a: out)
    ctx = FeatureContext([pdf], log)
    params = rotate.FEATURE.prepare(ctx)
    assert params == (90, [1], out) and "invalid page spec" in log.lines[0]
    rotate.FEATURE.run(ctx, params)
    with pymupdf.open(out) as doc:
        assert [p.rotation for p in doc] == [0, 90, 0]


def test_rotate_feature_all_pages(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf, out = make_pdf("a.pdf", 2), tmp_path / "r.pdf"
    monkeypatch.setattr(rotate, "ask_choice", lambda *a: "180")
    monkeypatch.setattr(rotate, "ask_text", lambda *a: "  ")
    monkeypatch.setattr(rotate, "save_pdf_path", lambda *a: out)
    ctx = FeatureContext([pdf], log)
    params = rotate.FEATURE.prepare(ctx)
    assert params == (180, None, out)
    rotate.FEATURE.run(ctx, params)
    assert "rotated all page(s) by 180" in log.lines[-1]


@pytest.mark.parametrize("choice, spec, save", [(None, "1", "x"), ("90", None, "x"), ("90", "1", None)])
def test_rotate_prepare_cancel(make_pdf, tmp_path: Path, log, monkeypatch, choice, spec, save):
    monkeypatch.setattr(rotate, "ask_choice", lambda *a: choice)
    monkeypatch.setattr(rotate, "ask_text", lambda *a: spec)
    monkeypatch.setattr(rotate, "save_pdf_path", lambda *a: tmp_path / "r.pdf" if save else None)
    assert rotate.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None


# --- compress ---------------------------------------------------------------
def test_compress_feature(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf = make_pdf("a.pdf", 2)
    monkeypatch.setattr(compress, "ask_choice", lambda *a: "Strong (100 dpi)")
    monkeypatch.setattr(compress, "choose_directory", lambda *a: tmp_path)
    ctx = FeatureContext([pdf], log)
    params = compress.FEATURE.prepare(ctx)
    assert params == (100, 60, tmp_path)
    compress.FEATURE.run(ctx, params)
    assert page_count(tmp_path / "a-small.pdf") == 2 and "MB ->" in log.lines[0]


def test_compress_prepare_cancel(make_pdf, log, monkeypatch):
    monkeypatch.setattr(compress, "ask_choice", lambda *a: None)
    assert compress.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None
    monkeypatch.setattr(compress, "ask_choice", lambda *a: "Light (200 dpi)")
    monkeypatch.setattr(compress, "choose_directory", lambda *a: None)
    assert compress.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None


# --- to_images --------------------------------------------------------------
def test_to_images_feature(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf = make_pdf("a.pdf", 2)
    monkeypatch.setattr(to_images, "ask_int", lambda *a: 72)
    monkeypatch.setattr(to_images, "choose_directory", lambda *a: tmp_path / "png")
    ctx = FeatureContext([pdf], log)
    params = to_images.FEATURE.prepare(ctx)
    to_images.FEATURE.run(ctx, params)
    assert sorted(p.name for p in (tmp_path / "png").iterdir()) == ["a-p001.png", "a-p002.png"]


def test_to_images_prepare_cancel(make_pdf, log, monkeypatch):
    monkeypatch.setattr(to_images, "ask_int", lambda *a: None)
    assert to_images.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None
    monkeypatch.setattr(to_images, "ask_int", lambda *a: 72)
    monkeypatch.setattr(to_images, "choose_directory", lambda *a: None)
    assert to_images.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None


# --- watermark --------------------------------------------------------------
def test_watermark_feature(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf = make_pdf("a.pdf", 1)
    monkeypatch.setattr(watermark, "ask_text", lambda *a: "DRAFT")
    monkeypatch.setattr(watermark, "choose_directory", lambda *a: tmp_path)
    ctx = FeatureContext([pdf], log)
    params = watermark.FEATURE.prepare(ctx)
    watermark.FEATURE.run(ctx, params)
    with pymupdf.open(tmp_path / "a-stamped.pdf") as doc:
        assert "DRAFT" in doc[0].get_text()


@pytest.mark.parametrize("text, folder", [(None, "x"), ("", "x"), ("DRAFT", None)])
def test_watermark_prepare_cancel(make_pdf, tmp_path: Path, log, monkeypatch, text, folder):
    monkeypatch.setattr(watermark, "ask_text", lambda *a: text)
    monkeypatch.setattr(watermark, "choose_directory", lambda *a: tmp_path if folder else None)
    assert watermark.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None


# --- replace_text -----------------------------------------------------------
def test_replace_text_feature(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf = make_pdf("a.pdf", 2)
    answers = iter(["page", "leaf"])
    monkeypatch.setattr(replace_text, "ask_text", lambda *a: next(answers))
    monkeypatch.setattr(replace_text, "ask_choice", lambda *a: "Match case")
    monkeypatch.setattr(replace_text, "choose_directory", lambda *a: tmp_path)
    ctx = FeatureContext([pdf], log)
    params = replace_text.FEATURE.prepare(ctx)
    assert params == ("page", "leaf", True, tmp_path)
    replace_text.FEATURE.run(ctx, params)
    with pymupdf.open(tmp_path / "a-replaced.pdf") as doc:
        assert all("leaf" in p.get_text() and "page" not in p.get_text() for p in doc)
    assert log.lines == [f"a.pdf: 2 replacement(s) -> {tmp_path / 'a-replaced.pdf'}"]


@pytest.mark.parametrize("old, new, case, folder", [(None, "y", "Match case", "x"), ("", "y", "Match case", "x"),
                                                    ("x", None, "Match case", "x"), ("x", "y", None, "x"),
                                                    ("x", "y", "Match case", None)])
def test_replace_text_prepare_cancel(make_pdf, tmp_path: Path, log, monkeypatch, old, new, case, folder):
    answers = iter([old, new])
    monkeypatch.setattr(replace_text, "ask_text", lambda *a: next(answers))
    monkeypatch.setattr(replace_text, "ask_choice", lambda *a: case)
    monkeypatch.setattr(replace_text, "choose_directory", lambda *a: tmp_path if folder else None)
    assert replace_text.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None


# --- to_docx ----------------------------------------------------------------
def test_to_docx_feature(make_pdf, tmp_path: Path, log, monkeypatch):
    pytest.importorskip("pdf2docx")
    pdf = make_pdf("a.pdf", 1)
    monkeypatch.setattr(to_docx, "choose_directory", lambda *a: tmp_path)
    ctx = FeatureContext([pdf], log)
    to_docx.FEATURE.run(ctx, to_docx.FEATURE.prepare(ctx))
    assert (tmp_path / "a.docx").exists()


# --- error handling ---------------------------------------------------------
def test_merge_same_stem_from_different_dirs(make_pdf, tmp_path: Path, log):
    a = make_pdf("doc.pdf", 2)
    other = tmp_path / "other"
    other.mkdir()
    b = other / "doc.png"
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
    pix.save(b)
    out = tmp_path / "m.pdf"
    merge.FEATURE.run(FeatureContext([a, b, a], log), (out, IMAGE_SIZE, MATCH))
    assert page_count(out) == 5


def test_batch_continues_after_bad_file(make_pdf, tmp_path: Path, log):
    good = make_pdf("good.pdf", 1)
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(RuntimeError, match="1 of 2"):
        watermark.FEATURE.run(FeatureContext([bad, good], log), ("X", tmp_path))
    assert (tmp_path / "good-stamped.pdf").exists()
    assert log.lines[0].startswith("ERROR: bad.pdf:") and "stamped" in log.lines[1]


def test_create_pdf_numbers_a_taken_target(make_pdf, make_png, tmp_path: Path, log):
    png = make_png("pic.png")
    existing = make_pdf("pic.pdf", 3)
    create_pdf.FEATURE.run(FeatureContext([png], log), (IMAGE_SIZE, MATCH))
    assert page_count(existing) == 3  # the file that was already there is untouched
    assert (tmp_path / "pic (2).pdf").exists() and "pic (2).pdf" in log.lines[0]


def test_to_docx_numbers_a_taken_target(make_pdf, tmp_path: Path, log):
    pdf = make_pdf("a.pdf", 1)
    (tmp_path / "a.docx").write_bytes(b"original")
    to_docx.FEATURE.run(FeatureContext([pdf], log), tmp_path)
    assert (tmp_path / "a.docx").read_bytes() == b"original"
    assert (tmp_path / "a (2).docx").exists()


def test_create_pdf_page_size_prompt(make_pdf, make_png, log, monkeypatch):
    asked: list[str] = []

    def ask(parent, title, prompt, options):
        asked.append(prompt)
        return options[0] if prompt.startswith("Put") else "Landscape"

    monkeypatch.setattr(create_pdf, "ask_choice", ask)
    # No image in the queue: no question, and the default page size comes back.
    assert create_pdf.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) == (IMAGE_SIZE, MATCH)
    assert asked == []
    # An image: the size is asked, and AUTO settles orientation by itself.
    assert create_pdf.FEATURE.prepare(FeatureContext([make_png()], log)) == (AUTO, MATCH)
    assert asked == ["Put images on:"]


def test_create_pdf_asks_orientation_for_a_fixed_size(make_png, log, monkeypatch):
    answers = iter(["A4", "Landscape"])
    monkeypatch.setattr(create_pdf, "ask_choice", lambda *a: next(answers))
    assert create_pdf.FEATURE.prepare(FeatureContext([make_png()], log)) == ("A4", "Landscape")


def test_create_pdf_cancel(make_png, log, monkeypatch):
    monkeypatch.setattr(create_pdf, "ask_choice", lambda *a: None)
    assert create_pdf.FEATURE.prepare(FeatureContext([make_png()], log)) is None
    answers = iter(["A4", None])
    monkeypatch.setattr(create_pdf, "ask_choice", lambda *a: next(answers))
    assert create_pdf.FEATURE.prepare(FeatureContext([make_png()], log)) is None


def test_extract_pages_prompt_carries_hint(make_pdf, tmp_path: Path, log, monkeypatch):
    prompts: list[str] = []
    answers = iter(["abc", "1"])

    def ask(parent, title, prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(extract_pages, "ask_text", ask)
    monkeypatch.setattr(extract_pages, "save_pdf_path", lambda *a: tmp_path / "e.pdf")
    extract_pages.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 2)], log))
    assert not prompts[0].startswith("Invalid") and prompts[1].startswith("Invalid: 'abc' is not a page number")


# --- add_text / add_image ---------------------------------------------------
class _FakeDialog:
    """Stands in for PlaceDialog: no Qt, canned answers."""

    accept = True
    result: tuple = ()

    def __init__(self, parent, src: Path, mode: str):
        self.src, self.mode = src, mode

    def exec(self) -> bool:
        return type(self).accept

    def params(self) -> tuple:
        return type(self).result


def _fake_dialog(monkeypatch, module, accept: bool, result: tuple = ()):
    fake = type("_D", (_FakeDialog,), {"accept": accept, "result": result})
    monkeypatch.setattr(module, "PlaceDialog", fake)
    return fake


def test_add_text_prepare_and_run(make_pdf, tmp_path: Path, log, monkeypatch):
    pdf = make_pdf("a.pdf", 2)
    _fake_dialog(monkeypatch, add_text, True, ("PAID", (72.0, 144.0), "2", "helv", 30, (1, 0, 0)))
    monkeypatch.setattr(add_text, "choose_directory", lambda *a: tmp_path)
    ctx = FeatureContext([pdf], log)
    params = add_text.FEATURE.prepare(ctx)
    assert params == ("PAID", (72.0, 144.0), "2", "helv", 30, (1, 0, 0), tmp_path)
    add_text.FEATURE.run(ctx, params)
    with pymupdf.open(tmp_path / "a-text.pdf") as doc:
        assert "PAID" in doc[1].get_text() and "PAID" not in doc[0].get_text()
    assert "text on 1 page(s)" in log.lines[-1]


def test_add_text_blank_spec_is_every_page(make_pdf, tmp_path: Path, log):
    ctx = FeatureContext([make_pdf("a.pdf", 3)], log)
    add_text.FEATURE.run(ctx, ("X", (72.0, 72.0), "", "helv", 12, (0, 0, 0), tmp_path))
    with pymupdf.open(tmp_path / "a-text.pdf") as doc:
        assert all("X" in page.get_text() for page in doc)
    assert "text on all page(s)" in log.lines[-1]


def test_add_text_spec_checked_per_file(make_pdf, tmp_path: Path, log):
    short, long = make_pdf("short.pdf", 1), make_pdf("long.pdf", 4)
    params = ("X", (72.0, 72.0), "4", "helv", 12, (0, 0, 0), tmp_path)
    with pytest.raises(RuntimeError, match="1 of 2"):
        add_text.FEATURE.run(FeatureContext([short, long], log), params)
    assert (tmp_path / "long-text.pdf").exists() and not (tmp_path / "short-text.pdf").exists()
    assert log.lines[0].startswith("ERROR: short.pdf:") and "outside 1-1" in log.lines[0]


def test_add_image_prepare_and_run(make_pdf, make_png, tmp_path: Path, log, monkeypatch):
    pdf, png = make_pdf("a.pdf", 2), make_png("pic.png", 20)
    _fake_dialog(monkeypatch, add_image, True, (png, (50.0, 50.0, 110.0, 110.0), "1"))
    monkeypatch.setattr(add_image, "choose_directory", lambda *a: tmp_path)
    ctx = FeatureContext([pdf], log)
    params = add_image.FEATURE.prepare(ctx)
    assert params == (png, (50.0, 50.0, 110.0, 110.0), "1", tmp_path)
    add_image.FEATURE.run(ctx, params)
    with pymupdf.open(tmp_path / "a-image.pdf") as doc:
        assert doc[0].get_images() and not doc[1].get_images()
    assert "pic.png on 1 page(s)" in log.lines[-1]


@pytest.mark.parametrize("module, result", [(add_text, ("X", (1.0, 1.0), "1", "helv", 12, (0, 0, 0))),
                                           (add_image, (Path("p.png"), (1.0, 1.0, 2.0, 2.0), "1"))])
@pytest.mark.parametrize("accepted", [False, True])
def test_place_prepare_cancel(make_pdf, log, monkeypatch, module, result, accepted):
    """Cancelling the dialog, or the folder chooser after it, both mean no work."""
    _fake_dialog(monkeypatch, module, accepted, result)
    monkeypatch.setattr(module, "choose_directory", lambda *a: None)
    assert module.FEATURE.prepare(FeatureContext([make_pdf("a.pdf", 1)], log)) is None
