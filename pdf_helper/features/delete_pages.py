"""Drop a page range from a single PDF - the inverse of Extract pages."""

from pathlib import Path

from pdf_helper.core.pdf import page_count, select_pages
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext
from pdf_helper.ui.dialogs import ask_page_spec, save_pdf_path


def prepare(ctx: FeatureContext) -> tuple[list[int], Path] | None:
    src = ctx.files[0]
    total = page_count(src)
    drop = ask_page_spec(ctx.parent, "Delete pages", total, ctx.log)
    if drop is None:
        return None
    keep = [i for i in range(total) if i not in set(drop)]
    if not keep:
        raise ValueError("that would delete every page")
    out = save_pdf_path(ctx.parent, src.with_name(f"{src.stem}-trimmed.pdf"))
    return (keep, out) if out else None


def run(ctx: FeatureContext, params: tuple[list[int], Path]) -> None:
    keep, out = params
    src = ctx.files[0]
    select_pages(src, keep, out)
    ctx.outputs.append(out)
    ctx.log(f"deleted {page_count(src) - len(keep)} page(s), {len(keep)} left -> {out}")


FEATURE = Feature(
    label="Delete pages", prepare=prepare, run=run, max_files=1, exts=PDF_ONLY, group="Pages",
    tooltip="Queue exactly one PDF, then choose the pages to drop",
)
