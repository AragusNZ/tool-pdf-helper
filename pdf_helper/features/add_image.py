"""Place an image at a point clicked on a page preview."""

from pathlib import Path

from pdf_helper.core.pages import parse_page_spec
from pdf_helper.core.pdf import page_count
from pdf_helper.core.stamp import add_image
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_output
from pdf_helper.ui.place_dialog import PlaceDialog


def prepare(ctx: FeatureContext) -> tuple | None:
    dialog = PlaceDialog(ctx.parent, ctx.files[0], "image")
    if not dialog.exec():
        return None
    name = ask_output(ctx.parent, ctx.files, "-image")
    return (*dialog.params(), name) if name else None


def run(ctx: FeatureContext, params: tuple) -> None:
    image, rect, spec, name = params

    def one(src: Path) -> Path:
        pages = parse_page_spec(spec, page_count(src)) if spec else None
        out = name(src)
        add_image(src, out, image, rect, pages)
        ctx.log(f"{src.name}: {image.name} on {'all' if pages is None else len(pages)} page(s) -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Add image", prepare=prepare, run=run, exts=PDF_ONLY, group="Stamp",
    tooltip="Click a spot on the page, set the width in mm",
)
