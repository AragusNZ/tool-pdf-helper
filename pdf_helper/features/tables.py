"""Pull the tables out of each PDF as CSV."""

from pathlib import Path

from pdf_helper.core.extract import extract_tables
from pdf_helper.core.paths import fresh
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import choose_directory


def prepare(ctx: FeatureContext) -> Path | None:
    return choose_directory(ctx.parent, ctx.files[0].parent)


def run(ctx: FeatureContext, base: Path) -> None:
    def one(src: Path) -> None:
        out_dir = fresh(base / f"{src.stem}-tables")
        written = extract_tables(src, out_dir)
        ctx.log(f"{src.name}: {len(written)} table(s) -> {out_dir}" if written else f"{src.name}: no tables found")

    each_file(ctx, one)


FEATURE = Feature(
    label="Tables to CSV", prepare=prepare, run=run, exts=PDF_ONLY,
    tooltip="One CSV per detected table, into <name>-tables/",
)
