"""Turn a PDF grey, for cheaper printing."""

from pathlib import Path

from pdf_helper.core.pdf import grayscale
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_output


def prepare(ctx: FeatureContext) -> Namer | None:
    return ask_output(ctx.parent, ctx.files, "-grey")


def run(ctx: FeatureContext, name: Namer) -> None:
    def one(src: Path) -> Path:
        out = name(src)
        grayscale(src, out)
        ctx.log(f"{src.name}: grey -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Grayscale", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="Convert every colour to grey",
)
