"""Several stamps on one PDF, saved once. An edit is a JSON-ready dict with a ``kind`` and that kind's fields."""

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pdf_helper.core.pages import parse_page_spec
from pdf_helper.core.pdf import _not_source, page_count
from pdf_helper.core.replace import replace_text
from pdf_helper.core.stamp import add_image, add_text, page_numbers, watermark

Op = dict[str, Any]
EDITS_EXT = ".pdfedits.json"


def _pages(spec: str, src: Path) -> list[int] | None:
    return parse_page_spec(spec, page_count(src)) if spec else None


def _text(src: Path, out: Path, op: Op) -> None:
    add_text(src, out, op["text"], tuple(op["pos"]), _pages(op["pages"], src),
             fontname=op["font"], size=op["size"], color=tuple(op["color"]))


def _image(src: Path, out: Path, op: Op) -> None:
    add_image(src, out, Path(op["image"]), tuple(op["rect"]), _pages(op["pages"], src))


def _numbers(src: Path, out: Path, op: Op) -> None:
    page_numbers(src, out, fmt=op["fmt"], position=op["position"])


def _watermark(src: Path, out: Path, op: Op) -> None:
    watermark(src, op["text"], out)


def _replace(src: Path, out: Path, op: Op) -> str:
    n = replace_text(src, op["old"], op["new"], out, case_sensitive=op["case_sensitive"])
    return f"{n} replacement(s)"


_APPLY: dict[str, Callable[[Path, Path, Op], str | None]] = {
    "text": _text, "image": _image, "numbers": _numbers, "watermark": _watermark, "replace": _replace,
}


def apply_edits(src: Path, out: Path, ops: list[Op]) -> list[str]:
    """Apply ``ops`` in order to ``src`` and write ``out``. Returns a note per op that has one (replacement counts)."""
    _not_source(out, [src])
    if not ops:
        raise ValueError("no edits")
    notes: list[str] = []
    # ponytail: every op re-saves to a temp file; refactor core to doc-level functions if it ever gets slow.
    with tempfile.TemporaryDirectory() as tmp:
        cur = src
        for i, op in enumerate(ops):
            nxt = out if i == len(ops) - 1 else Path(tmp) / f"{i}.pdf"
            note = _APPLY[op["kind"]](cur, nxt, op)
            if note:
                notes.append(note)
            cur = nxt
    return notes


def describe(op: Op) -> str:
    """One line for the editor's list."""
    kind = op["kind"]
    where = f"on pages {op['pages']}" if op.get("pages") else "on all pages"
    if kind == "text":
        return f'Text "{op["text"]}" {where}'
    if kind == "image":
        return f"Image {Path(op['image']).name} {where}"
    if kind == "numbers":
        return f"Page numbers: {op['fmt'].format(n=1, total=10)}, {op['position']}"
    if kind == "watermark":
        return f'Watermark "{op["text"]}"'
    return f'Replace "{op["old"]}" with "{op["new"]}"' + (" (match case)" if op["case_sensitive"] else "")


def save_edits(path: Path, ops: list[Op]) -> None:
    path.write_text(json.dumps(ops, indent=2), encoding="utf-8")


def load_edits(path: Path) -> list[Op]:
    """The edits a ``save_edits`` file holds. A file of another shape is refused with a clear message."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(op, dict) and op.get("kind") in _APPLY for op in data):
        raise ValueError(f"{path.name} is not an edits file")
    return data
