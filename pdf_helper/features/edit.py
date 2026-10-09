"""Add text, images, page numbers or a watermark and replace text - several at once - then save once per file."""

from pathlib import Path

from pdf_helper.core.edit import Op, apply_edits
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer
from pdf_helper.ui.edit_dialog import EditDialog


def prepare(ctx: FeatureContext) -> tuple[list[Op], Namer] | None:
    dialog = EditDialog(ctx.parent, ctx.files)  # asks where to write itself, so a cancelled Save keeps the edits
    accepted = dialog.exec()
    dialog.deleteLater()
    return (dialog.ops, dialog.namer) if accepted else None


def run(ctx: FeatureContext, params: tuple[list[Op], Namer]) -> None:
    ops, name = params

    def one(src: Path) -> Path:
        out = name(src)
        notes = apply_edits(src, out, ops)
        ctx.log(f"{src.name}: {len(ops)} edit(s)" + (f" ({', '.join(notes)})" if notes else "") + f" -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Edit", prepare=prepare, run=run, exts=PDF_ONLY, group="Edit",
    tooltip="Add text, images, page numbers or a watermark and replace text - several at once, saved as one file",
)
