from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QListWidget

from pdf_helper.core.convert import is_supported


class FileQueue(QListWidget):
    """Ordered list of files. Accepts drops from Explorer, drag to reorder."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.model().rowsMoved.connect(self.changed)

    def paths(self) -> list[Path]:
        return [Path(self.item(i).text()) for i in range(self.count())]

    def add_paths(self, paths: list[Path]) -> list[Path]:
        """Add existing supported files (directories expanded one level). Returns what was skipped."""
        skipped: list[Path] = []
        existing = set(self.paths())
        for p in paths:
            candidates = sorted(c for c in p.iterdir() if c.is_file()) if p.is_dir() else [p]
            for c in candidates:
                if not c.is_file() or not is_supported(c):
                    skipped.append(c)
                elif c not in existing:
                    self.addItem(str(c))
                    existing.add(c)
        self.changed.emit()
        return skipped

    def remove_selected(self) -> None:
        for item in self.selectedItems():
            self.takeItem(self.row(item))
        self.changed.emit()

    def clear(self) -> None:  # type: ignore[override]
        super().clear()
        self.changed.emit()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            self.add_paths([Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()])
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
