"""Convert PDFs to Word documents."""

from pathlib import Path

from pdf_helper.core.docx import to_docx
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_output


def prepare(ctx: FeatureContext) -> Namer | None:
    return ask_output(ctx.parent, ctx.files, "", ".docx")


def run(ctx: FeatureContext, name: Namer) -> None:
    def one(src: Path) -> Path:
        out = name(src)
        to_docx(src, out)
        ctx.log(f"{src.name} -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(label="PDF to Word", prepare=prepare, run=run, exts=PDF_ONLY, tooltip="Convert to .docx (layout is approximate)")
