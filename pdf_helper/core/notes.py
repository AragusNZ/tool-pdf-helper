"""Turn reviewer comments into numbered footnotes: a marker per comment, notes pages, links, bookmarks."""

import html
import io
from collections import Counter
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
INDENT = 12  # notes page: quote, comment and author sit in from the number; replies twice that
DISC = (0.85, 0.85, 0.85)  # light grey, the usual disc
PLACEMENTS = ("after", "end", "only")
MARKERS = ("right", "left", "inline", "start")


@dataclass(frozen=True)
class NotesOptions:
    quote: bool = False  # prefix each note with the text under the highlight
    uncommented: bool = False  # list highlights that have no comment too, quote only
    authors: bool = False  # append the reviewer's name to each note
    bake: bool = False  # flatten the annotations into the page
    placement: str = "after"  # notes "after" each page, all at the "end", or notes "only" with no source pages
    marker: str = "right"  # number in the "right" or "left" margin, "inline" after the phrase, or at the "start" on the highlight
    export: bool = False  # also write a Markdown file of the notes
    mark_size: float = MARK_SIZE  # points, for the number on the page
    mark_color: tuple[float, float, float] = MARK_COLOR  # RGB 0-1, for the number on the page and on the notes page
    disc: tuple[float, float, float] | None = None  # fill of a disc behind the number on the page; None for no disc
    heading: str = "Notes for"  # notes page heading, followed by "page N"
    leader: bool = False  # thin line from the highlight's nearest edge to a margin number, which then sits in a bubble


@dataclass
class Note:
    page: int  # 0-based source page
    start: pymupdf.Point  # where the annotation begins, for ordering and the back link
    end: pymupdf.Point  # upper-right of its last quad, for an inline marker
    first: pymupdf.Rect  # its first line (first quad), whose edges a leader line leaves from
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
            first = pymupdf.Quad(annot.vertices[:4]).rect
        else:
            start, end, first = annot.rect.tl, annot.rect.tr, annot.rect
        block = next((i for i, b in enumerate(blocks) if b.contains(start)), len(blocks))
        note = Note(page.number, start, end, first, quote, comment, _text(annot.info.get("title")), replies.get(annot.xref, []))
        found.append((block, start.y, note))
    return [note for _, _, note in sorted(found, key=lambda f: f[:2])]


def _stamp(page: pymupdf.Page, notes: list[Note], opts: NotesOptions) -> None:
    """Write each note's number on the page and remember where.

    Margin numbers are laid out top to bottom by where their highlight starts, whatever the reading
    order, so a right-column note that sits above a left-column one is not pushed below it.
    """
    margin = opts.marker in ("right", "left")
    last_y = -opts.mark_size
    for note in sorted(notes, key=lambda n: n.start.y) if margin else notes:
        label = str(note.n)
        size = opts.mark_size
        width = pymupdf.get_text_length(label, fontname="hebo", fontsize=size)
        bubble = opts.leader and margin  # outline round the number, closing the leader
        radius = max(width, size) / 2 + 2 if opts.disc or bubble else 0
        if opts.marker == "inline":
            at = note.end + (1 + radius - width / 2 if radius else 1, size * 0.7)
        elif opts.marker == "start":  # on the highlight, tucked into its top-left corner
            at = note.start + (radius - width / 2 if radius else 1, radius + size * 0.35 if radius else size * 0.85)
        else:
            x = page.rect.x1 - max(MARK_INSET, width + 4, radius * 2) if opts.marker == "right" else page.rect.x0 + 6
            step = radius * 2 + 2 if radius else size
            last_y = max(note.start.y + size, last_y + step)
            at = pymupdf.Point(x, last_y)
        note.mark = pymupdf.Rect(at.x, at.y - size, at.x + width, at.y + 2)
        if radius:
            center = pymupdf.Point(at.x + width / 2, at.y - size * 0.35)
            note.mark = pymupdf.Rect(center.x - radius, center.y - radius, center.x + radius, center.y + radius)
        if opts.leader and margin:  # highlight's near edge, mid-line, to the number's near edge
            right = opts.marker == "right"
            edge = pymupdf.Point(note.first.x1 if right else note.first.x0, (note.first.y0 + note.first.y1) / 2)
            tip = pymupdf.Point(note.mark.x0 - 1 if right else note.mark.x1 + 1, (note.mark.y0 + note.mark.y1) / 2)
            page.draw_line(edge, tip, color=opts.mark_color, width=0.5)
        if radius:
            page.draw_circle(center, radius, color=opts.mark_color if bubble else None, fill=opts.disc, width=0.5)
        page.insert_text(at, label, fontsize=size, fontname="hebo", color=opts.mark_color)


def _css(opts: NotesOptions) -> str:
    rgb = "#" + "".join(f"{round(c * 255):02x}" for c in opts.mark_color)
    return (
        "body {font-family: sans-serif; font-size: 10pt; color: #222} "
        "h1 {font-size: 18pt; margin: 0 0 14pt 0} "
        "h2 {font-size: 14pt; margin: 0 0 8pt 0; padding-bottom: 3pt; border-bottom: 0.6pt solid #999} "
        "p {margin: 0} "
        f"p.num {{font-size: 11pt; font-weight: bold; color: {rgb}; margin: 10pt 0 2pt 0}} "
        f"p.quote {{font-style: italic; color: #555; margin: 0 0 3pt {INDENT}pt}} "
        f"p.comment {{margin: 0 0 0 {INDENT}pt}} "
        f"p.by {{font-size: 8.5pt; color: #777; margin: 2pt 0 0 {INDENT}pt}} "
        f"p.reply {{font-size: 9.5pt; margin: 3pt 0 0 {INDENT * 2}pt}}"
    )


def _esc(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")


def _item_html(note: Note, opts: NotesOptions) -> str:
    out = f'<p class="num">{note.n}</p>'
    if note.quote:
        out += f'<p class="quote">\u201c{_esc(note.quote)}\u201d</p>'
    if note.comment:
        out += f'<p class="comment">{_esc(note.comment)}</p>'
    if opts.authors and note.author:
        out += f'<p class="by">\u2014 {_esc(note.author)}</p>'
    for author, reply in note.replies:
        out += f'<p class="reply">&#8627; {f"<b>{_esc(author)}:</b> " if author else ""}{_esc(reply)}</p>'
    return out


def _notes_pages(
    size: pymupdf.Rect, sections: list[tuple[str, list[Note]]], opts: NotesOptions, title: str = "",
) -> pymupdf.Document:
    """Pages of ``size`` holding each heading and its notes, as many pages as the text needs."""
    body = f"<h1>{html.escape(title)}</h1>" if title else ""
    body += "".join(f"<h2>{html.escape(heading)}</h2>" + "".join(_item_html(n, opts) for n in notes)
                    for heading, notes in sections)
    story = pymupdf.Story(html=body, user_css=_css(opts))
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
    pages = []
    for i in range(first, first + count):
        words = doc[i].get_text("words")
        per_line = Counter((w[5], w[6]) for w in words)
        pages.append((i, [w for w in words if per_line[(w[5], w[6])] == 1 and w[0] < MARGIN + 20]))  # alone on its line
    for note in notes:
        label = str(note.n)
        hit = next(((i, w) for i, words in pages for w in words if w[4] == label), None)
        if hit is None:  # pragma: no cover - Story always writes the number on its own line
            continue
        i, word = hit
        line = pymupdf.Rect(word[:4])
        doc[i].insert_link({"kind": pymupdf.LINK_GOTO, "from": line, "page": source[note.page],
                            "to": pymupdf.Point(0, max(note.start.y - 20, 0))})
        if note.mark is not None:
            doc[source[note.page]].insert_link({"kind": pymupdf.LINK_GOTO, "from": note.mark, "page": i,
                                                "to": pymupdf.Point(0, max(line.y0 - 20, 0))})


def _heading(opts: NotesOptions, page: int) -> str:
    """``opts.heading`` then "page N"; "Page N" alone when the prefix is blank."""
    text = f"{opts.heading.strip()} page {page + 1}".strip()
    return text[0].upper() + text[1:]


def notes_markdown(name: str, notes: list[Note], opts: NotesOptions) -> str:
    lines = [f"# Notes for {name}", ""]
    page = None
    for note in notes:
        if note.page != page:
            page = note.page
            lines += [f"## {_heading(opts, page)}", ""]
        text = note.comment.replace("\n", " ")
        if note.quote:
            text = f"“{note.quote}” — {text}" if text else f"“{note.quote}”"
        if opts.authors and note.author:
            text += f" — {note.author}"
        lines.append(f"{note.n}. {text}")
        lines += [f"    - ↳ {f'{a}: ' if a else ''}{r.replace(chr(10), ' ')}" for a, r in note.replies]
        lines.append("")
    return "\n".join(lines)


def footnote_comments(src: Path, out: Path, opts: NotesOptions | None = None, *, md: Path | None = None) -> int:
    """Number every reviewer comment, follow the pages with notes, link the two and bookmark the notes.

    Numbers run through the whole file. Returns how many notes were written; raises when there are none.
    ``md`` also receives the notes as Markdown.
    """
    opts = opts if opts is not None else NotesOptions()
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
            sections = [(_heading(opts, p), ns) for p, ns in by_page.items()]
            with _notes_pages(doc[0].rect, sections, opts, title=f"Notes for {src.name}") as only:
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
                with _notes_pages(doc[source[p]].rect, [(_heading(opts, p), notes)], opts) as pages:
                    doc.insert_pdf(pages, start_at=first)
                    added += pages.page_count
                    blocks.append((notes, first, pages.page_count, _heading(opts, p)))
        else:
            source = {p: p for p in by_page}
            first = doc.page_count
            sections = [(_heading(opts, p), ns) for p, ns in by_page.items()]
            with _notes_pages(doc[0].rect, sections, opts, title="Notes") as pages:
                doc.insert_pdf(pages)
                blocks.append((all_notes, first, pages.page_count, "Notes"))
        for notes, first, count, _ in blocks:
            _link(doc, notes, source, first, count)
        toc = doc.get_toc()  # read after inserting, so existing entries carry their shifted page numbers
        doc.set_toc(toc + [[1, title, first + 1] for _, first, _, title in blocks])
        doc.save(out)
    return n
