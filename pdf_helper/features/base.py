"""Feature contract. A feature is a button; the app knows nothing else about it."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pdf_helper.core.convert import is_supported

PDF_ONLY = frozenset({".pdf"})


@dataclass
class FeatureContext:
    files: list[Path]
    log: Callable[[str], None]
    parent: Any = None  # QWidget, only for dialogs in prepare()


@dataclass
class Feature:
    label: str
    run: Callable[[FeatureContext, Any], None]  # worker thread; must not touch Qt
    prepare: Callable[[FeatureContext], Any] | None = None  # UI thread; return None to cancel
    min_files: int = 1
    max_files: int | None = None
    exts: frozenset[str] | None = None  # None = any supported extension
    tooltip: str = ""

    def enabled_for(self, files: list[Path]) -> bool:
        n = len(files)
        if n < self.min_files or (self.max_files is not None and n > self.max_files):
            return False
        if self.exts is None:
            return all(is_supported(f) for f in files)
        return all(f.suffix.lower() in self.exts for f in files)


def each_file(ctx: FeatureContext, fn: Callable[[Path], None]) -> None:
    """Run ``fn`` on every queued file. A failure is logged and the batch continues."""
    failed = 0
    for src in ctx.files:
        try:
            fn(src)
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the rest
            logging.getLogger(__name__).exception("%s failed", src)
            ctx.log(f"ERROR: {src.name}: {exc or type(exc).__name__}")
            failed += 1
    if failed:
        raise RuntimeError(f"{failed} of {len(ctx.files)} file(s) failed")
