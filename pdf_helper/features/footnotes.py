"""Number each reviewer comment and add notes pages listing them."""

from pathlib import Path

from pdf_helper.core.notes import NotesOptions, footnote_comments
from pdf_helper.core.paths import fresh
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import ask_options, choose_directory

PLACEMENT = {"After each page": "after", "At the end": "end", "Notes only, no source pages": "only"}
MARKER = {"Right margin": "right", "Left margin": "left", "After the phrase": "inline"}
SIZE = {"Small (7 pt)": 7, "Medium (9 pt)": 9, "Large (12 pt)": 12}
COLOUR = {"Red": (0.8, 0, 0), "Blue": (0, 0.3, 0.8), "Green": (0, 0.5, 0), "Orange": (0.9, 0.45, 0), "Black": (0, 0, 0)}
FIELDS: dict[str, bool | list[str]] = {
    "Each note holds": ["Comment only", "Quote the highlight, then the comment"],
    "Include highlights that have no comment": False,
    "Show reviewer name": False,
    "Highlights": ["Keep as annotations", "Flatten into the page"],
    "Notes go": list(PLACEMENT),
    "Number sits": list(MARKER),
    "Number size": list(SIZE),
    "Number colour": list(COLOUR),
    "Number in a grey circle": False,
    "Also write <name>-notes.md": False,
}


def prepare(ctx: FeatureContext) -> tuple[NotesOptions, Path] | None:
    answers = ask_options(ctx.parent, "Footnote comments", FIELDS)
    if answers is None:
        return None
    out_dir = choose_directory(ctx.parent, ctx.files[0].parent)
    if not out_dir:
        return None
    opts = NotesOptions(
        quote=answers["Each note holds"] != "Comment only",
        uncommented=bool(answers["Include highlights that have no comment"]),
        authors=bool(answers["Show reviewer name"]),
        bake=answers["Highlights"] != "Keep as annotations",
        placement=PLACEMENT[str(answers["Notes go"])],
        marker=MARKER[str(answers["Number sits"])],
        export=bool(answers["Also write <name>-notes.md"]),
        mark_size=SIZE[str(answers["Number size"])],
        mark_color=COLOUR[str(answers["Number colour"])],
        circle=bool(answers["Number in a grey circle"]),
    )
    return opts, out_dir


def run(ctx: FeatureContext, params: tuple[NotesOptions, Path]) -> None:
    opts, out_dir = params

    def one(src: Path) -> Path | list[Path]:
        out = fresh(out_dir / f"{src.stem}-notes.pdf")
        md = fresh(out_dir / f"{src.stem}-notes.md") if opts.export else None
        n = footnote_comments(src, out, opts, md=md)
        ctx.log(f"{src.name}: {n} note(s) -> {out}" + (f" and {md.name}" if md else ""))
        return [out, md] if md else out

    each_file(ctx, one)


FEATURE = Feature(
    label="Footnote comments", prepare=prepare, run=run, exts=PDF_ONLY, group="Text",
    tooltip="Number every comment on the page and add notes pages listing them, linked both ways",
)
