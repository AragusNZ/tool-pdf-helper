"""Diagonal text watermark on every page."""

from pathlib import Path

from pdf_helper.core.paths import fresh
from pdf_helper.core.stamp import watermark
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_text, choose_directory


def prepare(ctx: FeatureContext) -> tuple[str, Path] | None:
    text = ask_text(ctx.parent, "Watermark", "Watermark text:")
    if not text:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (text, out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[str, Path]) -> None:
    text, out_dir = params

    def one(src: Path) -> None:
        out = fresh(out_dir / f"{src.stem}-stamped.pdf")
        watermark(src, text, out)
        ctx.log(f"{src.name}: stamped -> {out}")

    each_file(ctx, one)


FEATURE = Feature(
    label="Watermark", prepare=prepare, run=run, exts=PDF_ONLY, group="Stamp",
    tooltip="Diagonal text on every page",
)
