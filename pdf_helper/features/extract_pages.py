"""Extract a page range from a single PDF."""

from pathlib import Path

from pdf_helper.core.pages import parse_page_spec
from pdf_helper.core.pdf import page_count, select_pages
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext
from pdf_helper.ui.dialogs import ask_text, save_pdf_path


def prepare(ctx: FeatureContext) -> tuple[list[int], Path] | None:
    src = ctx.files[0]
    total = page_count(src)
    hint = ""
    while True:
        spec = ask_text(ctx.parent, "Extract pages", f"{hint}Pages to extract (1-{total}), e.g. 1-3,5,8-:")
        if spec is None:
            return None
        try:
            pages = parse_page_spec(spec, total)
            break
        except ValueError as exc:
            ctx.log(f"invalid page spec: {exc}")
            hint = f"Invalid: {exc}\n"
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
    tooltip="Queue exactly one PDF, then choose the pages to keep",
)
