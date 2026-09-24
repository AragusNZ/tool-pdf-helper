"""Page image that reports where it was clicked, shared by the placement and redaction dialogs."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel

OUTLINE = QColor("#c0272d")


class PagePreview(QLabel):
    """Rendered page. Clicks and drawn boxes are in page points, not pixels."""

    clicked = Signal(float, float)

    def __init__(self):
        super().__init__(alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.base: QPixmap | None = None
        self._scale = 1.0

    def show_page(self, png: bytes, page_width: float) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(png, "PNG")
        self.base = pixmap
        self._scale = pixmap.width() / page_width
        self.setPixmap(pixmap)

    def draw_boxes(self, rects: list[tuple[float, float, float, float]], fill: QColor | None = None) -> None:
        """Redraw the page with each of ``rects`` (page points) outlined, or plain when empty."""
        if self.base is None:
            return
        pixmap = self.base.copy()
        if rects:
            painter = QPainter(pixmap)
            painter.setPen(QPen(OUTLINE, 2))
            if fill is not None:
                painter.setBrush(fill)
            s = self._scale
            for rect in rects:
                painter.drawRect(
                    round(rect[0] * s),
                    round(rect[1] * s),
                    round((rect[2] - rect[0]) * s),
                    round((rect[3] - rect[1]) * s),
                )
            painter.end()
        self.setPixmap(pixmap)

    def point_on_page(self, position) -> tuple[float, float] | None:
        """``position`` (widget pixels) in page points, or None when it is past the page image."""
        if self.base is None or not self.base.rect().contains(position.toPoint()):
            return None
        return position.x() / self._scale, position.y() / self._scale

    def clamped_point(self, position) -> tuple[float, float] | None:
        """``position`` in page points, pulled back onto the page when the drag left it."""
        if self.base is None:
            return None
        x = min(max(position.x(), 0), self.base.width())
        y = min(max(position.y(), 0), self.base.height())
        return x / self._scale, y / self._scale

    def mousePressEvent(self, event) -> None:
        # A click past the page image (the dialog is resizable) is not a point on the page.
        point = self.point_on_page(event.position())
        if point is not None:
            self.clicked.emit(*point)
