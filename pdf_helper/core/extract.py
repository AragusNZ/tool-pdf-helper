"""Pull embedded images, tables and plain text out of a PDF, and search it."""

import csv
from pathlib import Path

from pdf_helper.core.pdf import open_pdf


def extract_images(src: Path, out_dir: Path) -> list[Path]:
    """Write every embedded image once (deduped by xref) as p<page>-<n>.<ext>."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    seen: set[int] = set()
    with open_pdf(src) as doc:
        for page in doc:
            n = 0
            for info in page.get_images(full=True):
                xref = info[0]
                if xref in seen:
                    continue
                seen.add(xref)
                img = doc.extract_image(xref)
                if not img:
                    continue
                n += 1
                out = out_dir / f"p{page.number + 1:03d}-{n:02d}.{img['ext']}"
                out.write_bytes(img["image"])
                written.append(out)
    return written


def extract_text(src: Path) -> list[str]:
    """Plain reading-order text, one string per page."""
    with open_pdf(src) as doc:
        return [page.get_text("text") for page in doc]


def extract_tables(src: Path, out_dir: Path) -> list[Path]:
    """Write every detected table as p<page>-<n>.csv. Empty cells come out blank."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with open_pdf(src) as doc:
        for page in doc:
            for n, table in enumerate(page.find_tables().tables, start=1):
                rows = table.extract()
                if not rows:
                    continue
                out = out_dir / f"p{page.number + 1:03d}-{n:02d}.csv"
                # utf-8-sig: Excel reads a plain UTF-8 CSV as Latin-1 and mangles anything accented.
                with out.open("w", newline="", encoding="utf-8-sig") as fh:
                    csv.writer(fh).writerows([[cell or "" for cell in row] for row in rows])
                written.append(out)
    return written


def find_text(src: Path, needle: str, *, case_sensitive: bool = False) -> list[tuple[int, int]]:
    """Pages containing ``needle`` as (1-based page number, hit count). Matches inside words."""
    hits: list[tuple[int, int]] = []
    with open_pdf(src) as doc:
        for page in doc:
            rects = page.search_for(needle)  # search_for is case-insensitive
            if case_sensitive:
                rects = [r for r in rects if page.get_textbox(r).strip() == needle]
            if rects:
                hits.append((page.number + 1, len(rects)))
    return hits


def _rtf_unicode(code: int) -> str:
    """RTF \\uN takes a signed 16-bit value."""
    return f"\\u{code - 0x10000 if code > 0x7FFF else code}?"


def _rtf_escape(text: str) -> str:
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch in "\\{}":
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\par\n")
        elif ch == "\r":
            continue
        elif code < 128:
            out.append(ch)
        elif code > 0xFFFF:  # outside BMP: surrogate pair
            code -= 0x10000
            out.append(_rtf_unicode(0xD800 + (code >> 10)) + _rtf_unicode(0xDC00 + (code & 0x3FF)))
        else:
            out.append(_rtf_unicode(code))
    return "".join(out)


def write_rtf(pages: list[str], out: Path) -> None:
    """Minimal RTF 1.5 document: one paragraph per line, \\page between PDF pages."""
    body = "\\page\n".join(_rtf_escape(p) for p in pages)
    out.write_text(
        "{\\rtf1\\ansi\\ansicpg1252\\deff0{\\fonttbl{\\f0\\fswiss Calibri;}}\n\\f0\\fs22\n" + body + "\n}\n",
        encoding="ascii",
    )
