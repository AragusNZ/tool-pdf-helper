"""Split each PDF into files of N pages."""

from pathlib import Path

from pdf_helper.core.pdf import split
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_int, choose_directory


def prepare(ctx: FeatureContext) -> tuple[int, Path] | None:
    every = ask_int(ctx.parent, "Split PDF", "Pages per output file:", 1, 1, 10000)
    if every is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (every, out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[int, Path]) -> None:
    every, out_dir = params

    def one(src: Path) -> None:
        parts = split(src, every, out_dir)
        ctx.log(f"{src.name}: {len(parts)} file(s) -> {out_dir}")

    each_file(ctx, one)


FEATURE = Feature(
    label="Split", prepare=prepare, run=run, exts=PDF_ONLY, group="Pages",
    tooltip="Split into files of N pages",
)
