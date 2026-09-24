"""Put every page on a sheet of a chosen size."""

from pathlib import Path

from pdf_helper.core.convert import AUTO, IMAGE_SIZE, ORIENTATIONS, PAGE_SIZES
from pdf_helper.core.impose import impose
from pdf_helper.core.paths import fresh
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_choice, choose_directory

# The two image-only entries decide a size from the picture, which a PDF page has no equivalent of.
SIZES = {name: size for name, size in PAGE_SIZES.items() if name not in (AUTO, IMAGE_SIZE)}


def prepare(ctx: FeatureContext) -> tuple[str, str, Path] | None:
    size = ask_choice(ctx.parent, "Resize pages", "Page size:", list(SIZES))
    if size is None:
        return None
    orientation = ask_choice(ctx.parent, "Resize pages", "Orientation:", list(ORIENTATIONS))
    if orientation is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (size, orientation, out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[str, str, Path]) -> None:
    size, orientation, out_dir = params

    def one(src: Path) -> Path:
        out = fresh(out_dir / f"{src.stem}-{size.split()[0].lower()}.pdf")
        impose(src, out, size=SIZES[size], orientation=orientation)
        ctx.log(f"{src.name}: pages on {size} -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Resize pages", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="Scale every page onto A4, Letter or another sheet size",
)
