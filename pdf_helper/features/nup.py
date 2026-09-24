"""Put several pages on one sheet, for printing."""

from pathlib import Path

from pdf_helper.core.convert import PAGE_SIZES
from pdf_helper.core.impose import impose
from pdf_helper.core.paths import fresh
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_choice, choose_directory

LAYOUTS = {"2 per sheet": (2, 1), "4 per sheet": (2, 2), "9 per sheet": (3, 3)}
# ponytail: sheets are A4. Add a size prompt if anyone prints Letter.
SHEET = PAGE_SIZES["A4"]


def prepare(ctx: FeatureContext) -> tuple[int, int, Path] | None:
    choice = ask_choice(ctx.parent, "N-up", "Pages per sheet:", list(LAYOUTS))
    if choice is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (*LAYOUTS[choice], out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[int, int, Path]) -> None:
    cols, rows, out_dir = params

    def one(src: Path) -> None:
        out = fresh(out_dir / f"{src.stem}-{cols * rows}up.pdf")
        impose(src, out, cols=cols, rows=rows, size=SHEET)
        ctx.log(f"{src.name}: {cols * rows} pages per A4 sheet -> {out}")

    each_file(ctx, one)


FEATURE = Feature(
    label="N-up", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="2, 4 or 9 pages on each A4 sheet",
)
