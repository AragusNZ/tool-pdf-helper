"""Stamp a page number on every page."""

from pathlib import Path

from pdf_helper.core.stamp import NUMBER_FORMATS, NUMBER_POSITIONS, page_numbers
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_choice, ask_output


def prepare(ctx: FeatureContext) -> tuple[str, str, Namer] | None:
    shown = ask_choice(ctx.parent, "Page numbers", "Show:", list(NUMBER_FORMATS))
    if shown is None:
        return None
    position = ask_choice(ctx.parent, "Page numbers", "Position:", list(NUMBER_POSITIONS))
    if position is None:
        return None
    name = ask_output(ctx.parent, ctx.files, "-numbered")
    return (NUMBER_FORMATS[shown], position, name) if name else None


def run(ctx: FeatureContext, params: tuple[str, str, Namer]) -> None:
    fmt, position, name = params

    def one(src: Path) -> Path:
        out = name(src)
        page_numbers(src, out, fmt=fmt, position=position)
        ctx.log(f"{src.name}: numbered -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Page numbers", prepare=prepare, run=run, exts=PDF_ONLY, group="Stamp",
    tooltip="Number every page, always starting at 1",
)
