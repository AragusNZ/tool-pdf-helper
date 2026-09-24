"""Stamp a page number on every page."""

from pathlib import Path

from pdf_helper.core.paths import fresh
from pdf_helper.core.stamp import NUMBER_FORMATS, NUMBER_POSITIONS, page_numbers
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_choice, choose_directory


def prepare(ctx: FeatureContext) -> tuple[str, str, Path] | None:
    shown = ask_choice(ctx.parent, "Page numbers", "Show:", list(NUMBER_FORMATS))
    if shown is None:
        return None
    position = ask_choice(ctx.parent, "Page numbers", "Position:", list(NUMBER_POSITIONS))
    if position is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (NUMBER_FORMATS[shown], position, out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[str, str, Path]) -> None:
    fmt, position, out_dir = params

    def one(src: Path) -> Path:
        out = fresh(out_dir / f"{src.stem}-numbered.pdf")
        page_numbers(src, out, fmt=fmt, position=position)
        ctx.log(f"{src.name}: numbered -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Page numbers", prepare=prepare, run=run, exts=PDF_ONLY, group="Stamp",
    tooltip="Number every page, always starting at 1",
)
