"""Extract a page range from a single PDF."""

from pathlib import Path

from pdf_helper.core.pdf import page_count, select_pages
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext
from pdf_helper.ui.dialogs import ask_page_spec, save_pdf_path


def prepare(ctx: FeatureContext) -> tuple[list[int], Path] | None:
    src = ctx.files[0]
    pages = ask_page_spec(ctx.parent, "Extract pages", page_count(src), ctx.log)
    if pages is None:
        return None
    out = save_pdf_path(ctx.parent, src.with_name(f"{src.stem}-pages.pdf"))
    return (pages, out) if out else None


def run(ctx: FeatureContext, params: tuple[list[int], Path]) -> None:
    pages, out = params
    select_pages(ctx.files[0], pages, out)
    ctx.log(f"extracted {len(pages)} page(s) -> {out}")


FEATURE = Feature(
    label="Extract pages",
    prepare=prepare,
    run=run,
    min_files=1,
    max_files=1,
    exts=PDF_ONLY,
    group="Pages",
    tooltip="Queue exactly one PDF, then choose the pages to keep. Spec order is kept, so 3,1,2 reorders",
)
