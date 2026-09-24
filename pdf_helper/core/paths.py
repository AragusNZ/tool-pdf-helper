"""Output naming. Nothing this tool writes ever replaces a file that is already there."""

from itertools import count
from pathlib import Path


def fresh(path: Path) -> Path:
    """``path`` if free, else the first ``<stem> (n)<suffix>`` that is. Works for folders too."""
    if not path.exists():
        return path
    for n in count(2):
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise AssertionError("unreachable")  # pragma: no cover
