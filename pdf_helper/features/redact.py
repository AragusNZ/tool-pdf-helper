"""Black out dragged areas and every occurrence of a phrase."""

from pathlib import Path

from pdf_helper.core.replace import redact
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_output
from pdf_helper.ui.redact_dialog import RedactDialog


def prepare(ctx: FeatureContext) -> tuple | None:
    dialog = RedactDialog(ctx.parent, ctx.files[0])
    if not dialog.exec():
        return None
    name = ask_output(ctx.parent, ctx.files, "-redacted")
    return (*dialog.params(), name) if name else None


def run(ctx: FeatureContext, params: tuple) -> None:
    boxes, needle, case_sensitive, name = params

    def one(src: Path) -> Path:
        out = name(src)
        n = redact(src, out, boxes, needle, case_sensitive=case_sensitive)
        ctx.log(f"{src.name}: {n} area(s) removed -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Redact", prepare=prepare, run=run, exts=PDF_ONLY, group="Text",
    tooltip="Drag boxes on the page preview, and/or remove every copy of a phrase",
)
