"""Put a password on PDFs."""

from pathlib import Path

from pdf_helper.core.pdf import protect
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_output, ask_password


def prepare(ctx: FeatureContext) -> tuple[str, Namer] | None:
    password = ask_password(ctx.parent, "Password protect", confirm=True)
    if password is None:
        return None
    name = ask_output(ctx.parent, ctx.files, "-protected")
    return (password, name) if name else None


def run(ctx: FeatureContext, params: tuple[str, Namer]) -> None:
    password, name = params  # never logged

    def one(src: Path) -> Path:
        out = name(src)
        protect(src, out, password)
        ctx.log(f"{src.name}: protected -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Password protect", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="Copy that needs a password to open (AES-256)",
)
