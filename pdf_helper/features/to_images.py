"""Render every page of each PDF to PNG."""

from pathlib import Path

from pdf_helper.core.render import render_pages
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_int, choose_directory


def prepare(ctx: FeatureContext) -> tuple[int, Path] | None:
    dpi = ask_int(ctx.parent, "PDF to images", "Resolution (DPI):", 150, 50, 600)
    if dpi is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (dpi, out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[int, Path]) -> None:
    dpi, out_dir = params

    def one(src: Path) -> Path:
        files = render_pages(src, out_dir, dpi=dpi)
        ctx.log(f"{src.name}: {len(files)} PNG(s) -> {out_dir}")
        return out_dir

    each_file(ctx, one)


FEATURE = Feature(label="PDF to images", prepare=prepare, run=run, exts=PDF_ONLY, tooltip="One PNG per page")
