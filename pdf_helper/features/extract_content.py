"""Dump each PDF's images to a folder and its text to an RTF file."""

from pathlib import Path

from pdf_helper.core.extract import extract_images, extract_text, write_rtf
from pdf_helper.core.paths import fresh
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import choose_directory


def prepare(ctx: FeatureContext) -> Path | None:
    return choose_directory(ctx.parent, ctx.files[0].parent)


def run(ctx: FeatureContext, base: Path) -> None:
    def one(src: Path) -> Path:
        out_dir = fresh(base / f"{src.stem}-content")
        images = extract_images(src, out_dir / "images")
        rtf = out_dir / f"{src.stem}.rtf"
        write_rtf(extract_text(src), rtf)
        ctx.log(f"{src.name}: {len(images)} image(s), text -> {rtf}")
        return out_dir

    each_file(ctx, one)


FEATURE = Feature(
    label="Extract content",
    prepare=prepare,
    run=run,
    exts=PDF_ONLY,
    tooltip="For each PDF: images to <name>-content/images/, text to <name>-content/<name>.rtf",
)
