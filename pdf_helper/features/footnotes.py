"""Number each reviewer comment and add notes pages listing them."""

from pathlib import Path

from pdf_helper.core.notes import NotesOptions, footnote_comments
from pdf_helper.core.paths import fresh
from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
from pdf_helper.ui.dialogs import Namer, ask_options, ask_output

PLACEMENT = {"After each page": "after", "At the end": "end", "Notes only, no source pages": "only"}
MARKER = {"Right margin": "right", "Left margin": "left", "After the phrase": "inline", "On the highlight, top left": "start"}
SIZE = {"Small (7 pt)": 7, "Medium (9 pt)": 9, "Large (12 pt)": 12}
COLOUR = {"Red": "#cc0000", "Blue": "#004dcc", "Green": "#008000", "Orange": "#e67300", "Black": "#000000"}
DISC = {"Light grey": "#d9d9d9", "Pale yellow": "#fff3b0", "Pale blue": "#dbe9ff", "White": "#ffffff"}
FIELDS: dict[str, bool | str | list[str] | dict[str, str]] = {
    "Each note holds": ["Comment only", "Quote the highlight, then the comment"],
    "Include highlights that have no comment": False,
    "Show reviewer name": False,
    "Highlights": ["Keep as annotations", "Flatten into the page"],
    "Notes go": list(PLACEMENT),
    "Notes heading, before the page number": "Notes for",
    "Number sits": list(MARKER),
    "Line from highlight to a margin number": False,
    "Number size": list(SIZE),
    "Number colour": COLOUR,
    "Number in a disc": False,
    "Disc colour": DISC,
    "Also write <name>-notes.md": False,
}


def _rgb(hex_color: str) -> tuple[float, float, float]:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return r, g, b


def prepare(ctx: FeatureContext) -> tuple[NotesOptions, Namer] | None:
    answers = ask_options(ctx.parent, "Footnote comments", FIELDS)
    if answers is None:
        return None
    name = ask_output(ctx.parent, ctx.files, "-notes")
    if not name:
        return None
    opts = NotesOptions(
        quote=answers["Each note holds"] != "Comment only",
        uncommented=bool(answers["Include highlights that have no comment"]),
        authors=bool(answers["Show reviewer name"]),
        bake=answers["Highlights"] != "Keep as annotations",
        placement=PLACEMENT[str(answers["Notes go"])],
        heading=str(answers["Notes heading, before the page number"]),
        marker=MARKER[str(answers["Number sits"])],
        leader=bool(answers["Line from highlight to a margin number"]),
        export=bool(answers["Also write <name>-notes.md"]),
        mark_size=SIZE[str(answers["Number size"])],
        mark_color=_rgb(str(answers["Number colour"])),
        disc=_rgb(str(answers["Disc colour"])) if answers["Number in a disc"] else None,
    )
    return opts, name


def run(ctx: FeatureContext, params: tuple[NotesOptions, Namer]) -> None:
    opts, name = params

    def one(src: Path) -> Path | list[Path]:
        out = name(src)
        md = fresh(out.with_suffix(".md")) if opts.export else None
        n = footnote_comments(src, out, opts, md=md)
        ctx.log(f"{src.name}: {n} note(s) -> {out}" + (f" and {md.name}" if md else ""))
        return [out, md] if md else out

    each_file(ctx, one)


FEATURE = Feature(
    label="Footnote comments", prepare=prepare, run=run, exts=PDF_ONLY, group="Text",
    tooltip="Number every comment on the page and add notes pages listing them, linked both ways",
)
