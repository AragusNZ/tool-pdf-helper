"""Edit title, author, subject and keywords."""

from pathlib import Path

from pdf_helper.core.paths import fresh
from pdf_helper.core.pdf import metadata, set_metadata
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_fields, choose_directory

FIELDS = {"Title": "title", "Author": "author", "Subject": "subject", "Keywords": "keywords"}


def prepare(ctx: FeatureContext) -> tuple[dict[str, str], Path] | None:
    # One file: show what it has. A batch: start blank, since the files differ.
    current = metadata(ctx.files[0]) if len(ctx.files) == 1 else {}
    answers = ask_fields(ctx.parent, "Edit info", {label: current.get(key, "") for label, key in FIELDS.items()})
    if answers is None:
        return None
    # ponytail: blank means "leave as is", so a field cannot be cleared; add a clear checkbox if asked.
    fields = {FIELDS[label]: value for label, value in answers.items() if value.strip()}
    if not fields:
        ctx.log("Edit info: nothing entered")
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (fields, out_dir) if out_dir else None


def run(ctx: FeatureContext, params: tuple[dict[str, str], Path]) -> None:
    fields, out_dir = params

    def one(src: Path) -> Path:
        out = fresh(out_dir / f"{src.stem}-info.pdf")
        set_metadata(src, out, fields)
        ctx.log(f"{src.name}: {', '.join(fields)} set -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Edit info", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
    tooltip="Title, author, subject and keywords. Blank fields are left as they are",
)
