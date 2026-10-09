"""Shrink PDFs by downsampling images and cleaning up."""

from pathlib import Path

from pdf_helper.core.pdf import compress
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_choice, ask_output

PRESETS = {"Light (200 dpi)": (200, 85), "Medium (150 dpi)": (150, 75), "Strong (100 dpi)": (100, 60)}


def prepare(ctx: FeatureContext) -> tuple[int, int, Namer] | None:
    choice = ask_choice(ctx.parent, "Compress", "Image quality:", list(PRESETS))
    if choice is None:
        return None
    name = ask_output(ctx.parent, ctx.files, "-small")
    return (*PRESETS[choice], name) if name else None


def run(ctx: FeatureContext, params: tuple[int, int, Namer]) -> None:
    dpi, quality, name = params

    def one(src: Path) -> Path:
        out = name(src)
        compress(src, out, dpi=dpi, quality=quality)
        before, after = src.stat().st_size, out.stat().st_size
        ctx.log(f"{src.name}: {before / 1e6:.2f} MB -> {after / 1e6:.2f} MB ({out})")
        if after >= before:
            ctx.log(f"  {src.name}: no smaller than the original - its images were already at or below {dpi} dpi")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Compress", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="Reduce file size",
)
