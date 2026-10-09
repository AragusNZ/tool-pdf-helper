"""Diagonal text watermark on every page."""

from pathlib import Path

from pdf_helper.core.stamp import watermark
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_output, ask_text


def prepare(ctx: FeatureContext) -> tuple[str, Namer] | None:
    text = (ask_text(ctx.parent, "Watermark", "Watermark text:") or "").strip()
    if not text:
        return None
    name = ask_output(ctx.parent, ctx.files, "-stamped")
    return (text, name) if name else None


def run(ctx: FeatureContext, params: tuple[str, Namer]) -> None:
    text, name = params

    def one(src: Path) -> Path:
        out = name(src)
        watermark(src, text, out)
        ctx.log(f"{src.name}: stamped -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Watermark", prepare=prepare, run=run, exts=PDF_ONLY, group="Stamp",
    tooltip="Diagonal text on every page",
)
