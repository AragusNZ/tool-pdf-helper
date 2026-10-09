"""Remove the password from PDFs, given the password."""

from pathlib import Path

from pdf_helper.core.pdf import unlock
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_output, ask_password


def prepare(ctx: FeatureContext) -> tuple[str, Namer] | None:
    password = ask_password(ctx.parent, "Unlock", confirm=False)
    if password is None:
        return None
    name = ask_output(ctx.parent, ctx.files, "-unlocked")
    return (password, name) if name else None


def run(ctx: FeatureContext, params: tuple[str, Namer]) -> None:
    password, name = params  # never logged

    def one(src: Path) -> Path:
        out = name(src)
        unlock(src, out, password)
        ctx.log(f"{src.name}: unlocked -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Unlock", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="Copy without the password - you need to know it",
)
