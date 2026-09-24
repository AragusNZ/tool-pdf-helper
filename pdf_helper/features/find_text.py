"""Report which pages of which queued PDFs contain a phrase. Writes nothing."""

from pathlib import Path

from pdf_helper.core.extract import find_text
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_choice, ask_text

SHOWN = 20  # pages listed before the line is cut short; a long report belongs in the log, not one line


def prepare(ctx: FeatureContext) -> tuple[str, bool] | None:
    needle = (ask_text(ctx.parent, "Find text", "Find:") or "").strip()
    if not needle:
        return None
    case = ask_choice(ctx.parent, "Find text", "Case:", ["Ignore case", "Match case"])
    return (needle, case == "Match case") if case else None


def run(ctx: FeatureContext, params: tuple[str, bool]) -> None:
    needle, case_sensitive = params

    def one(src: Path) -> None:
        hits = find_text(src, needle, case_sensitive=case_sensitive)
        if not hits:
            ctx.log(f"{src.name}: not found")
            return
        listed = [f"p{page} x{n}" if n > 1 else f"p{page}" for page, n in hits[:SHOWN]]
        if len(hits) > SHOWN:
            listed.append(f"and {len(hits) - SHOWN} more")
        ctx.log(f"{src.name}: {sum(n for _, n in hits)} hit(s) on {len(hits)} page(s) - {', '.join(listed)}")

    each_file(ctx, one)


FEATURE = Feature(
    label="Find text", prepare=prepare, run=run, exts=PDF_ONLY, group="Text",
    tooltip="List the pages holding a phrase, in the log. Matches inside words",
)
