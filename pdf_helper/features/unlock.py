"""Remove the password from PDFs, given the password."""

from pathlib import Path

from pdf_helper.core.paths import fresh
from pdf_helper.core.pdf import unlock
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_password, choose_directory


def prepare(ctx: FeatureContext) -> tuple[str, Path] | None:
    password = ask_password(ctx.parent, "Unlock", confirm=False)
    if password is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (password, out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[str, Path]) -> None:
    password, out_dir = params  # never logged

    def one(src: Path) -> Path:
        out = fresh(out_dir / f"{src.stem}-unlocked.pdf")
        unlock(src, out, password)
        ctx.log(f"{src.name}: unlocked -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Unlock", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="Copy without the password - you need to know it",
)
