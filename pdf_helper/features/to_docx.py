"""Convert PDFs to Word documents."""

from pathlib import Path

from pdf_helper.core.docx import to_docx
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import choose_directory


def prepare(ctx: FeatureContext) -> Path | None:
    return choose_directory(ctx.parent, ctx.files[0].parent)


def run(ctx: FeatureContext, out_dir: Path) -> None:
    def one(src: Path) -> None:
        out = out_dir / f"{src.stem}.docx"
        if out.exists():
            ctx.log(f"skip {src.name}: {out.name} already exists")
            return
        to_docx(src, out)
        ctx.log(f"{src.name} -> {out}")

    each_file(ctx, one)


FEATURE = Feature(label="PDF to Word", prepare=prepare, run=run, exts=PDF_ONLY, tooltip="Convert to .docx (layout is approximate)")
