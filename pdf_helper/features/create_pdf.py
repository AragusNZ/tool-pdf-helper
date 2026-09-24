"""Convert each queued file to a PDF beside it."""

from pathlib import Path

from pdf_helper.core.convert import AUTO, IMAGE_EXTS, IMAGE_SIZE, MATCH, ORIENTATIONS, PAGE_SIZES, to_pdf
from pdf_helper.features.base import Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_choice


def ask_page_size(ctx: FeatureContext) -> tuple[str, str] | None:
    """Page size and orientation for images, asked only when the queue holds one. Shared with Merge."""
    if not any(f.suffix.lower() in IMAGE_EXTS for f in ctx.files):
        return (IMAGE_SIZE, MATCH)
    size = ask_choice(ctx.parent, "Page size", "Put images on:", list(PAGE_SIZES))
    if size is None:
        return None
    if size in (AUTO, IMAGE_SIZE):  # both decide orientation from the image
        return (size, MATCH)
    orientation = ask_choice(ctx.parent, "Page size", "Orientation:", list(ORIENTATIONS))
    return (size, orientation) if orientation else None


def prepare(ctx: FeatureContext) -> tuple[str, str] | None:
    return ask_page_size(ctx)


def run(ctx: FeatureContext, params: tuple[str, str]) -> None:
    page_size, orientation = params

    def one(src: Path) -> Path | None:
        if src.suffix.lower() == ".pdf":
            ctx.log(f"skip {src.name} (already PDF)")
            return None
        out = to_pdf(src, src.parent, log=ctx.log, page_size=page_size, orientation=orientation)
        ctx.log(f"created {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(label="Create PDF(s)", prepare=prepare, run=run, tooltip="Convert each file to a PDF next to it")
