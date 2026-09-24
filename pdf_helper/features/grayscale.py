"""Turn a PDF grey, for cheaper printing."""

from pathlib import Path

from pdf_helper.core.paths import fresh
from pdf_helper.core.pdf import grayscale
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import choose_directory


def prepare(ctx: FeatureContext) -> Path | None:
    return choose_directory(ctx.parent, ctx.files[0].parent)


def run(ctx: FeatureContext, out_dir: Path) -> None:
    def one(src: Path) -> Path:
        out = fresh(out_dir / f"{src.stem}-grey.pdf")
        grayscale(src, out)
        ctx.log(f"{src.name}: grey -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Grayscale", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="Convert every colour to grey",
)
