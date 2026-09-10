"""Shrink PDFs by downsampling images and cleaning up."""

from pathlib import Path

from pdf_helper.core.pdf import compress
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_choice, choose_directory

PRESETS = {"Light (200 dpi)": (200, 85), "Medium (150 dpi)": (150, 75), "Strong (100 dpi)": (100, 60)}


def prepare(ctx: FeatureContext) -> tuple[int, int, Path] | None:
    choice = ask_choice(ctx.parent, "Compress", "Image quality:", list(PRESETS))
    if choice is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (*PRESETS[choice], out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[int, int, Path]) -> None:
    dpi, quality, out_dir = params

    def one(src: Path) -> None:
        out = out_dir / f"{src.stem}-small.pdf"
        compress(src, out, dpi=dpi, quality=quality)
        before, after = src.stat().st_size, out.stat().st_size
        ctx.log(f"{src.name}: {before / 1e6:.2f} MB -> {after / 1e6:.2f} MB ({out})")

    each_file(ctx, one)


FEATURE = Feature(label="Compress", prepare=prepare, run=run, exts=PDF_ONLY, tooltip="Reduce file size")
