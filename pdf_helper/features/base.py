"""Feature contract. A feature is a button; the app knows nothing else about it."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pdf_helper.core.convert import is_supported

PDF_ONLY = frozenset({".pdf"})


@dataclass
class FeatureContext:
    files: list[Path]
    log: Callable[[str], None]
    parent: Any = None  # QWidget, only for dialogs in prepare()
    outputs: list[Path] = field(default_factory=list)  # what the run wrote; the app offers to open its folder
    progress: Callable[[int, int], None] = lambda done, total: None
    cancelled: Callable[[], bool] = lambda: False  # polled between files


@dataclass
class Feature:
    label: str
    run: Callable[[FeatureContext, Any], None]  # worker thread; must not touch Qt
    prepare: Callable[[FeatureContext], Any] | None = None  # UI thread; return None to cancel
    min_files: int = 1
    max_files: int | None = None
    exts: frozenset[str] | None = None  # None = any supported extension
    tooltip: str = ""
    group: str = "Convert"  # the Actions tab this button lives on, in registry order

    def enabled_for(self, files: list[Path]) -> bool:
        n = len(files)
        if n < self.min_files or (self.max_files is not None and n > self.max_files):
            return False
        if self.exts is None:
            return all(is_supported(f) for f in files)
        return all(f.suffix.lower() in self.exts for f in files)


def each_file(ctx: FeatureContext, fn: Callable[[Path], Path | list[Path] | None]) -> None:
    """Run ``fn`` on every queued file. A failure is logged and the batch continues.

    ``fn`` returns the file or folder it wrote (or None); those land in ``ctx.outputs``.
    A cancel is honoured between files, never mid-file, so no half-written output is left behind.
    """
    failed = 0
    total = len(ctx.files)
    for i, src in enumerate(ctx.files):
        if ctx.cancelled():
            ctx.log(f"cancelled: {i} of {total} file(s) done")
            break
        try:
            written = fn(src)
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the rest
            logging.getLogger(__name__).exception("%s failed", src)
            ctx.log(f"ERROR: {src.name}: {exc or type(exc).__name__}")
            failed += 1
        else:
            if written is not None:
                ctx.outputs.extend(written if isinstance(written, list) else [written])
        ctx.progress(i + 1, total)
    if failed:
        raise RuntimeError(f"{failed} of {total} file(s) failed")
