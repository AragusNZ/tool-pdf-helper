"""Rotate all or some pages of one PDF."""

from pathlib import Path

from pdf_helper.core.pages import parse_page_spec
from pdf_helper.core.pdf import page_count, rotate
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext
from pdf_helper.ui.dialogs import ask_choice, ask_text, save_pdf_path


def prepare(ctx: FeatureContext) -> tuple[int, list[int] | None, Path] | None:
    src = ctx.files[0]
    choice = ask_choice(ctx.parent, "Rotate", "Rotate clockwise by:", ["90", "180", "270"])
    if choice is None:
        return None
    total = page_count(src)
    hint = ""
    while True:
        spec = ask_text(ctx.parent, "Rotate", f"{hint}Pages (1-{total}, e.g. 1-3,5; blank = all):")
        if spec is None:
            return None
        if not spec.strip():
            pages = None
            break
        try:
            pages = parse_page_spec(spec, total)
            break
        except ValueError as exc:
            ctx.log(f"invalid page spec: {exc}")
            hint = f"Invalid: {exc}\n"
    out = save_pdf_path(ctx.parent, src.with_name(f"{src.stem}-rotated.pdf"))
    return (int(choice), pages, out) if out else None


def run(ctx: FeatureContext, params: tuple[int, list[int] | None, Path]) -> None:
    degrees, pages, out = params
    rotate(ctx.files[0], degrees, pages, out)
    ctx.log(f"rotated {'all' if pages is None else len(pages)} page(s) by {degrees} -> {out}")


FEATURE = Feature(label="Rotate", prepare=prepare, run=run, max_files=1, exts=PDF_ONLY, tooltip="Rotate pages of one PDF")
