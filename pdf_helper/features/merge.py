"""Merge all queued files, in queue order, into one PDF."""

import tempfile
from pathlib import Path

from pdf_helper.core.convert import to_pdf
from pdf_helper.core.pdf import merge
from pdf_helper.features.base import Feature, FeatureContext
from pdf_helper.features.create_pdf import ask_page_size
from pdf_helper.ui.dialogs import save_pdf_path


def prepare(ctx: FeatureContext) -> tuple[Path, str, str] | None:
    out = save_pdf_path(ctx.parent, ctx.files[0].with_name("merged.pdf"))
    if out is None:
        return None
    chosen = ask_page_size(ctx)
    return (out, *chosen) if chosen else None


def run(ctx: FeatureContext, params: tuple[Path, str, str]) -> None:
    out, page_size, orientation = params
    with tempfile.TemporaryDirectory() as tmp:
        pdfs = []
        for i, src in enumerate(ctx.files):
            ctx.log(f"preparing {src.name}")
            work = Path(tmp, str(i))  # own dir per input: two inputs with the same stem must not collide
            work.mkdir()
            pdfs.append(to_pdf(src, work, log=ctx.log, page_size=page_size, orientation=orientation))
        merge(pdfs, out)
    ctx.outputs.append(out)
    ctx.log(f"merged {len(pdfs)} files -> {out}")


FEATURE = Feature(
    label="Merge to one PDF",
    prepare=prepare,
    run=run,
    min_files=2,
    tooltip="Combine all queued files (PDF or not) into a single PDF, in queue order",
)
