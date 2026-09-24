"""Find and replace text in each queued PDF."""

from pathlib import Path

from pdf_helper.core.paths import fresh
from pdf_helper.core.replace import replace_text
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_choice, ask_text, choose_directory

Params = tuple[str, str, bool, Path]


def prepare(ctx: FeatureContext) -> Params | None:
    old = ask_text(ctx.parent, "Replace text", "Find:")
    if not old:
        return None
    new = ask_text(ctx.parent, "Replace text", f"Replace '{old}' with:")
    if new is None:
        return None
    case = ask_choice(ctx.parent, "Replace text", "Case:", ["Ignore case", "Match case"])
    if case is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    return (old, new, case == "Match case", out_dir) if out_dir else None


def run(ctx: FeatureContext, params: Params) -> None:
    old, new, case_sensitive, out_dir = params

    def one(src: Path) -> Path:
        out = fresh(out_dir / f"{src.stem}-replaced.pdf")
        n = replace_text(src, old, new, out, case_sensitive=case_sensitive)
        ctx.log(f"{src.name}: {n} replacement(s) -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Replace text", prepare=prepare, run=run, exts=PDF_ONLY, group="Text",
    tooltip="Find and replace text on every page",
)
