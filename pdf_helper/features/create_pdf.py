"""Convert each queued file to a PDF beside it."""

from pathlib import Path

from pdf_helper.core.convert import to_pdf
from pdf_helper.features.base import Feature, FeatureContext, each_file


def run(ctx: FeatureContext, _params) -> None:
    def one(src: Path) -> None:
        if src.suffix.lower() == ".pdf":
            ctx.log(f"skip {src.name} (already PDF)")
            return
        out = src.with_suffix(".pdf")
        if out.exists():
            ctx.log(f"skip {src.name}: {out.name} already exists")
            return
        ctx.log(f"created {to_pdf(src, src.parent, log=ctx.log)}")

    each_file(ctx, one)


FEATURE = Feature(label="Create PDF(s)", run=run, tooltip="Convert each file to a PDF next to it")
