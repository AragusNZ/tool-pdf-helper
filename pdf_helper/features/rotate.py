"""Rotate all or some pages of one PDF."""

from pathlib import Path

from pdf_helper.core.pdf import page_count, rotate
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext
from pdf_helper.ui.dialogs import ask_choice, ask_page_spec, save_pdf_path


def prepare(ctx: FeatureContext) -> tuple[int, list[int] | None, Path] | None:
    src = ctx.files[0]
    choice = ask_choice(ctx.parent, "Rotate", "Rotate clockwise by:", ["90", "180", "270"])
    if choice is None:
        return None
    chosen = ask_page_spec(ctx.parent, "Rotate", page_count(src), ctx.log, allow_blank=True)
    if chosen is None:
        return None
    pages = chosen or None
    out = save_pdf_path(ctx.parent, src.with_name(f"{src.stem}-rotated.pdf"))
    return (int(choice), pages, out) if out else None


def run(ctx: FeatureContext, params: tuple[int, list[int] | None, Path]) -> None:
    degrees, pages, out = params
    rotate(ctx.files[0], degrees, pages, out)
    ctx.outputs.append(out)
    ctx.log(f"rotated {'all' if pages is None else len(pages)} page(s) by {degrees} -> {out}")


FEATURE = Feature(
    label="Rotate", prepare=prepare, run=run, max_files=1, exts=PDF_ONLY, group="Pages",
    tooltip="Rotate pages of one PDF",
)
