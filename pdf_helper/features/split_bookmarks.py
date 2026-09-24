"""Split each PDF at its top-level bookmarks."""

from pathlib import Path

from pdf_helper.core.paths import fresh
from pdf_helper.core.pdf import split_by_toc
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import choose_directory


def prepare(ctx: FeatureContext) -> Path | None:
    return choose_directory(ctx.parent, ctx.files[0].parent)


def run(ctx: FeatureContext, base: Path) -> None:
    def one(src: Path) -> None:
        out_dir = fresh(base / f"{src.stem}-chapters")
        parts = split_by_toc(src, out_dir)
        ctx.log(f"{src.name}: {len(parts)} chapter(s) -> {out_dir}")

    each_file(ctx, one)


FEATURE = Feature(
    label="Split by bookmarks", prepare=prepare, run=run, exts=PDF_ONLY, group="Pages",
    tooltip="One file per top-level bookmark, into <name>-chapters/",
)
