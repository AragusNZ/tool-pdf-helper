"""Look and feel: asset lookup, the stylesheet, and the light/dark switch.

Colours are palette roles, never literals, so one stylesheet is correct in both schemes.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

SCHEMES = {
    "System": Qt.ColorScheme.Unknown,
    "Light": Qt.ColorScheme.Light,
    "Dark": Qt.ColorScheme.Dark,
}

STYLESHEET = """
QGroupBox {
    border: 1px solid palette(mid);
    border-radius: 6px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QPushButton {
    padding: 6px 12px;
    min-height: 20px;
    border: 1px solid palette(mid);
    border-radius: 4px;
    background: palette(button);
}
QPushButton:hover:enabled { background: palette(midlight); border-color: palette(highlight); }
QPushButton:pressed:enabled { background: palette(dark); }
QPushButton:disabled { color: palette(mid); border-color: palette(midlight); }
QListWidget, QPlainTextEdit {
    border: 1px solid palette(mid);
    border-radius: 4px;
}
QListWidget::item { padding: 3px 4px; }
QListWidget::item:selected { background: palette(highlight); color: palette(highlighted-text); }
QStatusBar::item { border: none; }
"""


def asset_path(name: str) -> Path:
    """Locate a bundled asset. PyInstaller --onefile unpacks them under sys._MEIPASS."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    return base / "pdf_helper" / "assets" / name


def _dark_palette() -> QPalette:
    """Fusion has no dark palette of its own, so spell one out."""
    window, base, alt = QColor("#2b2b2b"), QColor("#1e1e1e"), QColor("#323232")
    text, disabled, highlight = QColor("#e6e6e6"), QColor("#6f6f6f"), QColor("#2f6fb5")
    p = QPalette()
    for role, colour in (
        (QPalette.ColorRole.Window, window),
        (QPalette.ColorRole.Base, base),
        (QPalette.ColorRole.AlternateBase, alt),
        (QPalette.ColorRole.Button, QColor("#3a3a3a")),
        (QPalette.ColorRole.ToolTipBase, window),
        (QPalette.ColorRole.WindowText, text),
        (QPalette.ColorRole.Text, text),
        (QPalette.ColorRole.ButtonText, text),
        (QPalette.ColorRole.ToolTipText, text),
        (QPalette.ColorRole.BrightText, QColor("#ff5555")),
        (QPalette.ColorRole.Highlight, highlight),
        (QPalette.ColorRole.HighlightedText, QColor("#ffffff")),
        (QPalette.ColorRole.PlaceholderText, disabled),
        # Borders in the stylesheet come from these three.
        (QPalette.ColorRole.Dark, QColor("#1a1a1a")),
        (QPalette.ColorRole.Mid, QColor("#565656")),
        (QPalette.ColorRole.Midlight, QColor("#484848")),
    ):
        p.setColor(role, colour)
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return p


# The palette the platform handed us at startup, so 'System' has something to go back to.
_system_palette: QPalette | None = None


def apply_scheme(name: str) -> None:
    """Force light or dark, or hand control back to the OS with 'System'.

    setColorScheme alone is enough on Windows and macOS but does nothing under X11/Wayland, so the
    palette is set explicitly too. The cost is that 'System' restores the palette captured at
    startup rather than tracking a later OS theme change - restart to pick that up.
    """
    global _system_palette
    app = QApplication.instance()
    if app is None:
        return
    if _system_palette is None:
        _system_palette = QPalette(app.palette())

    QGuiApplication.styleHints().setColorScheme(SCHEMES.get(name, Qt.ColorScheme.Unknown))
    if name == "Dark":
        app.setPalette(_dark_palette())
    elif name == "Light":
        app.setPalette(QStyleFactory.create("Fusion").standardPalette())
    else:
        app.setPalette(_system_palette)
    app.setStyleSheet(STYLESHEET)  # re-resolve the palette(...) references against the new palette
