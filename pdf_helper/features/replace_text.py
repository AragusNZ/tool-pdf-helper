"""Find and replace text in each queued PDF."""

from pathlib import Path

from pdf_helper.core.replace import replace_text
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_choice, ask_output, ask_text

Params = tuple[str, str, bool, Namer]


def prepare(ctx: FeatureContext) -> Params | None:
    old = (ask_text(ctx.parent, "Replace text", "Find:") or "").strip()
    if not old:
        return None
    new = ask_text(ctx.parent, "Replace text", f"Replace '{old}' with:")
    if new is None:
        return None
    case = ask_choice(ctx.parent, "Replace text", "Case:", ["Ignore case", "Match case"])
    if case is None:
        return None
    name = ask_output(ctx.parent, ctx.files, "-replaced")
    return (old, new, case == "Match case", name) if name else None


def run(ctx: FeatureContext, params: Params) -> None:
    old, new, case_sensitive, name = params

    def one(src: Path) -> Path:
        out = name(src)
        n = replace_text(src, old, new, out, case_sensitive=case_sensitive)
        ctx.log(f"{src.name}: {n} replacement(s) -> {out}")
        return out

    each_file(ctx, one)


FEATURE = Feature(
    label="Replace text", prepare=prepare, run=run, exts=PDF_ONLY, group="Text",
    tooltip="Find and replace text on every page",
)
