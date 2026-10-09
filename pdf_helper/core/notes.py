"""Turn reviewer comments into numbered footnotes: a marker per comment, notes pages, links, bookmarks."""

import html
import io
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from pdf_helper.core.pdf import _not_source, open_pdf

# Text markup carries quads, so it has a start point and text under it; the rest anchor at their rect.
MARKUP = frozenset({pymupdf.PDF_ANNOT_HIGHLIGHT, pymupdf.PDF_ANNOT_UNDERLINE, pymupdf.PDF_ANNOT_SQUIGGLY,
                    pymupdf.PDF_ANNOT_STRIKE_OUT})
NOTE_TYPES = MARKUP | {pymupdf.PDF_ANNOT_TEXT, pymupdf.PDF_ANNOT_SQUARE, pymupdf.PDF_ANNOT_CIRCLE, pymupdf.PDF_ANNOT_LINE,
                       pymupdf.PDF_ANNOT_INK, pymupdf.PDF_ANNOT_POLYGON, pymupdf.PDF_ANNOT_POLY_LINE}
MARGIN = 36  # points around the notes page text
MARK_SIZE = 7
MARK_COLOR = (0.8, 0, 0)
MARK_INSET = 14  # points in from the page edge; a second margin mark on the same line stacks below the first
CSS = ("body {font-family: sans-serif; font-size: 10pt} h2 {font-size: 13pt} p {margin: 0 0 6pt 0} "
       "p.reply {margin-left: 14pt}")
PLACEMENTS = ("after", "end", "only")
MARKERS = ("right", "left", "inline")


@dataclass(frozen=True)
class NotesOptions:
    quote: bool = False  # prefix each note with the text under the highlight
    uncommented: bool = False  # list highlights that have no comment too, quote only
    authors: bool = False  # append the reviewer's name to each note
    bake: bool = False  # flatten the annotations into the page
    placement: str = "after"  # notes "after" each page, all at the "end", or notes "only" with no source pages
    marker: str = "right"  # number in the "right" or "left" margin, or "inline" after the phrase
    export: bool = False  # also write a Markdown file of the notes


@dataclass
class Note:
    page: int  # 0-based source page
    start: pymupdf.Point  # where the annotation begins, for ordering and the back link
    end: pymupdf.Point  # upper-right of its last quad, for an inline marker
    quote: str
    comment: str
    author: str
    replies: list[tuple[str, str]] = field(default_factory=list)  # (author, text)
    n: int = 0
    mark: pymupdf.Rect | None = None  # where the number was stamped


def _text(content: str | None) -> str:
    return (content or "").strip()


def _quoted(words: list, annot: pymupdf.Annot) -> str:
    """The page's words whose middle sits inside one of the annotation's quads.

    Per quad rather than ``annot.rect`` so a column neighbour is not swept in; by word middle so the
    overlapping line quads of a scanned page do not repeat a line.
    """
    quads = annot.vertices
    rects = [pymupdf.Quad(quads[i:i + 4]).rect for i in range(0, len(quads), 4)]

    def inside(word) -> bool:
        mid = (pymupdf.Point(word[0], word[1]) + pymupdf.Point(word[2], word[3])) / 2
        return any(r.contains(mid) for r in rects)

    return " ".join(w[4] for w in words if inside(w))


def _collect(page: pymupdf.Page, opts: NotesOptions) -> list[Note]:
    """The notes on ``page`` in reading order, replies folded under the annotation they answer.

    Reading order is the order of the text block holding the start, then y. Block order follows the
    content stream, which puts the left column before the right on a two-column page.
    """
    annots = {a.xref: a for a in page.annots() if a.type[0] in NOTE_TYPES}
    replies: dict[int, list[tuple[str, str]]] = {}
    roots = []
    for annot in annots.values():
        if not annot.irt_xref:
            roots.append(annot)
            continue
        root, seen = annot, set()
        while root.irt_xref in annots and root.xref not in seen:  # climb to the thread's root
            seen.add(root.xref)
            root = annots[root.irt_xref]
        if not root.irt_xref and _text(annot.info.get("content")):
            replies.setdefault(root.xref, []).append((_text(annot.info.get("title")), _text(annot.info.get("content"))))
    words = page.get_text("words") if opts.quote or opts.uncommented else []
    blocks = [pymupdf.Rect(b[:4]) for b in page.get_text("blocks")]
    found = []
    for annot in roots:
        comment = _text(annot.info.get("content"))
        markup = annot.type[0] in MARKUP
        quote = _quoted(words, annot) if markup and (opts.quote or (opts.uncommented and not comment)) else ""
        if not (comment or replies.get(annot.xref) or (opts.uncommented and quote)):
            continue
        if markup:
            start, end = pymupdf.Point(annot.vertices[0]), pymupdf.Point(annot.vertices[-3])  # ul of first quad, ur of last
        else:
            start, end = annot.rect.tl, annot.rect.tr
        block = next((i for i, b in enumerate(blocks) if b.contains(start)), len(blocks))
        note = Note(page.number, start, end, quote, comment, _text(annot.info.get("title")), replies.get(annot.xref, []))
        found.append((block, start.y, note))
    return [note for _, _, note in sorted(found, key=lambda f: f[:2])]


def _stamp(page: pymupdf.Page, notes: list[Note], opts: NotesOptions) -> None:
    """Write each note's number on the page and remember where."""
    last_y = -MARK_SIZE
    for note in notes:
        if opts.marker == "inline":
            at = note.end + (1, 5)
        else:
            x = page.rect.x1 - MARK_INSET if opts.marker == "right" else page.rect.x0 + 6
            last_y = max(note.start.y + MARK_SIZE, last_y + MARK_SIZE)
            at = pymupdf.Point(x, last_y)
        label = str(note.n)
        page.insert_text(at, label, fontsize=MARK_SIZE, fontname="hebo", color=MARK_COLOR)
        width = pymupdf.get_text_length(label, fontname="hebo", fontsize=MARK_SIZE)
        note.mark = pymupdf.Rect(at.x, at.y - MARK_SIZE, at.x + width, at.y + 2)


def _item_html(note: Note, opts: NotesOptions) -> str:
    def esc(text: str) -> str:
        return html.escape(text).replace("\n", "<br>")

    text = esc(note.comment)
    if note.quote:
        quoted = f"<i>“{esc(note.quote)}”</i>"
        text = f"{quoted} — {text}" if text else quoted
    if opts.authors and note.author:
        text += f" — {esc(note.author)}"
    out = f"<p><b>{note.n}.</b> {text}</p>"
    for author, reply in note.replies:
        out += f'<p class="reply">&#8627; {f"<b>{esc(author)}:</b> " if author else ""}{esc(reply)}</p>'
    return out


def _notes_pages(size: pymupdf.Rect, sections: list[tuple[str, list[Note]]], opts: NotesOptions) -> pymupdf.Document:
    """Pages of ``size`` holding each heading and its notes, as many pages as the text needs."""
    body = "".join(f"<h2>{html.escape(heading)}</h2>" + "".join(_item_html(n, opts) for n in notes)
                   for heading, notes in sections)
    story = pymupdf.Story(html=body, user_css=CSS)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    more = True
    while more:
        dev = writer.begin_page(size)
        more, _ = story.place(size + (MARGIN, MARGIN, -MARGIN, -MARGIN))
        story.draw(dev)
        writer.end_page()
    writer.close()
    return pymupdf.open("pdf", buf.getvalue())


def _link(doc: pymupdf.Document, notes: list[Note], source: dict[int, int], first: int, count: int) -> None:
    """Marker -> its line on a notes page, and the note's number -> back to the source page."""
    pages = [(i, doc[i].get_text("words")) for i in range(first, first + count)]
    for note in notes:
        label = f"{note.n}."
        # the number is the first word of its line, at the margin plus the body padding Story adds
        hit = next(((i, w) for i, words in pages for w in words if w[4] == label and w[7] == 0 and w[0] < MARGIN + 20), None)
        if hit is None:  # pragma: no cover - Story always starts the item with its number
            continue
        i, word = hit
        line = pymupdf.Rect(word[:4])
        doc[i].insert_link({"kind": pymupdf.LINK_GOTO, "from": line, "page": source[note.page],
                            "to": pymupdf.Point(0, max(note.start.y - 20, 0))})
        if note.mark is not None:
            doc[source[note.page]].insert_link({"kind": pymupdf.LINK_GOTO, "from": note.mark, "page": i,
                                                "to": pymupdf.Point(0, max(line.y0 - 20, 0))})


def notes_markdown(name: str, notes: list[Note], opts: NotesOptions) -> str:
    lines = [f"# Notes for {name}", ""]
    page = None
    for note in notes:
        if note.page != page:
            page = note.page
            lines += [f"## Page {page + 1}", ""]
        text = note.comment.replace("\n", " ")
        if note.quote:
            text = f"“{note.quote}” — {text}" if text else f"“{note.quote}”"
        if opts.authors and note.author:
            text += f" — {note.author}"
        lines.append(f"{note.n}. {text}")
        lines += [f"    - ↳ {f'{a}: ' if a else ''}{r.replace(chr(10), ' ')}" for a, r in note.replies]
        lines.append("")
    return "\n".join(lines)


def footnote_comments(src: Path, out: Path, opts: NotesOptions = NotesOptions(), *, md: Path | None = None) -> int:
    """Number every reviewer comment, follow the pages with notes, link the two and bookmark the notes.

    Numbers run through the whole file. Returns how many notes were written; raises when there are none.
    ``md`` also receives the notes as Markdown.
    """
    _not_source(out, [src])
    if opts.placement not in PLACEMENTS or opts.marker not in MARKERS:
        raise ValueError(f"unknown placement {opts.placement!r} or marker {opts.marker!r}")
    by_page: dict[int, list[Note]] = {}
    n = 0
    with open_pdf(src) as doc:
        for page in doc:
            notes = _collect(page, opts)
            if not notes:
                continue
            for note in notes:
                n += 1
                note.n = n
            if opts.placement != "only":
                _stamp(page, notes, opts)
            by_page[page.number] = notes
        if not by_page:
            raise ValueError("no comments found")
        all_notes = [note for notes in by_page.values() for note in notes]
        if md is not None:
            md.write_text(notes_markdown(src.name, all_notes, opts), encoding="utf-8")
        if opts.placement == "only":
            with _notes_pages(doc[0].rect, [(f"Page {p + 1}", ns) for p, ns in by_page.items()], opts) as only:
                only.save(out)
            return n
        if opts.bake:
            doc.bake(annots=True, widgets=False)
        source: dict[int, int] = {}  # original page index -> index once notes pages are in
        blocks: list[tuple[list[Note], int, int, str]] = []  # (notes, first notes page, page count, bookmark)
        if opts.placement == "after":
            added = 0
            for p, notes in by_page.items():
                source[p] = p + added
                first = p + 1 + added
                with _notes_pages(doc[p].rect, [(f"Notes for page {p + 1}", notes)], opts) as pages:
                    doc.insert_pdf(pages, start_at=first)
                    added += pages.page_count
                    blocks.append((notes, first, pages.page_count, f"Notes for page {p + 1}"))
        else:
            source = {p: p for p in by_page}
            first = doc.page_count
            with _notes_pages(doc[0].rect, [(f"Page {p + 1}", ns) for p, ns in by_page.items()], opts) as pages:
                doc.insert_pdf(pages)
                blocks.append((all_notes, first, pages.page_count, "Notes"))
        for notes, first, count, _ in blocks:
            _link(doc, notes, source, first, count)
        toc = doc.get_toc()  # read after inserting, so existing entries carry their shifted page numbers
        doc.set_toc(toc + [[1, title, first + 1] for _, first, _, title in blocks])
        doc.save(out)
    return n
