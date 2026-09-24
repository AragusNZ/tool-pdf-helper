"""Convert PDFs to Word documents."""

from pathlib import Path

from pdf_helper.core.docx import to_docx
from pdf_helper.core.paths import fresh
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import choose_directory


def prepare(ctx: FeatureContext) -> Path | None:
    return choose_directory(ctx.parent, ctx.files[0].parent)


def run(ctx: FeatureContext, out_dir: Path) -> None:
    def one(src: Path) -> Path:
        out = fresh(out_dir / f"{src.stem}.docx")
        to_docx(src, out)
        ctx.log(f"{src.name} -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(label="PDF to Word", prepare=prepare, run=run, exts=PDF_ONLY, tooltip="Convert to .docx (layout is approximate)")
