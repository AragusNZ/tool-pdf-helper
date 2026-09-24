"""Qt widgets and helpers, run offscreen."""

from pathlib import Path

import pymupdf
from PySide6.QtCore import QMimeData, QPointF, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pdf_helper.core.render import render_page_png
from pdf_helper.core.stamp import MM
from pdf_helper.ui import dialogs, theme
from pdf_helper.ui.place_dialog import PlaceDialog
from pdf_helper.ui.preview import PagePreview
from pdf_helper.ui.redact_dialog import DragPreview, RedactDialog
from pdf_helper.ui.file_queue import FileQueue
from pdf_helper.ui.worker import Worker


class _DropEvent:
    """Stand-in for QDropEvent: only what FileQueue reads."""

    def __init__(self, paths: list[Path] | None):
        self._mime = QMimeData()
        if paths is not None:
            self._mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
        self.accepted = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True


# --- FileQueue --------------------------------------------------------------
def test_queue_add_dedupe_and_skip(qapp, make_pdf, tmp_path: Path):
    q = FileQueue()
    pdf = make_pdf("a.pdf", 1)
    bad = tmp_path / "x.zip"
    bad.write_bytes(b"")
    fired = []
    q.changed.connect(lambda: fired.append(1))
    assert q.add_paths([pdf, pdf, bad]) == [bad]
    assert q.paths() == [pdf] and fired == [1]


def test_queue_rejects_a_file_that_is_not_there(qapp, tmp_path: Path):
    """A path typed into the dialog, or a file deleted since, must not enter the queue."""
    q = FileQueue()
    gone = tmp_path / "gone.pdf"
    assert q.add_paths([gone]) == [gone]
    assert q.paths() == []


def test_queue_expands_directory(qapp, make_pdf, tmp_path: Path):
    sub = tmp_path / "d"
    sub.mkdir()
    (sub / "b.pdf").write_bytes(make_pdf("a.pdf", 1).read_bytes())
    (sub / "notes.md").write_text("x")
    q = FileQueue()
    skipped = q.add_paths([sub])
    assert [p.name for p in q.paths()] == ["b.pdf"] and [p.name for p in skipped] == ["notes.md"]


def test_queue_remove_and_clear(qapp, make_pdf):
    q = FileQueue()
    a, b = make_pdf("a.pdf", 1), make_pdf("b.pdf", 1)
    q.add_paths([a, b])
    q.item(0).setSelected(True)
    q.remove_selected()
    assert q.paths() == [b]
    q.clear()
    assert q.paths() == []


def test_queue_drop_events(qapp, make_pdf):
    q = FileQueue()
    pdf = make_pdf("a.pdf", 1)
    enter = _DropEvent([pdf])
    q.dragEnterEvent(enter)
    q.dragMoveEvent(enter)
    assert enter.accepted
    drop = _DropEvent([pdf])
    q.dropEvent(drop)
    assert drop.accepted and q.paths() == [pdf]


def test_queue_non_url_drag_falls_through(qapp):
    q = FileQueue()
    ev = _DropEvent(None)
    # QListWidget's own handlers reject a bare stub; we only assert nothing was queued and no crash.
    for handler in (q.dragEnterEvent, q.dragMoveEvent, q.dropEvent):
        try:
            handler(ev)
        except TypeError:
            pass
    assert q.paths() == [] and not ev.accepted


# --- Worker -----------------------------------------------------------------
def test_worker_runs_and_reports_errors(qapp):
    seen: list[str] = []
    ran: list[int] = []
    w = Worker(lambda: ran.append(1))
    w.start()
    assert w.wait(5000) and ran == [1]

    def boom():
        raise ValueError("kaboom")

    w2 = Worker(boom)
    w2.failed.connect(seen.append)
    w2.start()
    assert w2.wait(5000)
    qapp.processEvents()
    assert seen == ["kaboom"]  # short message only; traceback goes to the log file


# --- dialogs ----------------------------------------------------------------
def test_save_pdf_path_adds_suffix(qapp, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", staticmethod(lambda *a: (str(tmp_path / "out"), "")))
    assert dialogs.save_pdf_path(None, tmp_path / "x.pdf") == tmp_path / "out.pdf"
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", staticmethod(lambda *a: (str(tmp_path / "o.PDF"), "")))
    assert dialogs.save_pdf_path(None, tmp_path / "x.pdf") == tmp_path / "o.PDF"
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", staticmethod(lambda *a: ("", "")))
    assert dialogs.save_pdf_path(None, tmp_path / "x.pdf") is None


def test_open_file_paths(qapp, monkeypatch):
    captured = {}

    def fake(parent, title, start, filt):
        captured["filter"] = filt
        return (["/a.pdf", "/b.png"], "")

    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileNames", staticmethod(fake))
    assert dialogs.open_file_paths(None, frozenset({".pdf", ".png"})) == [Path("/a.pdf"), Path("/b.png")]
    assert "*.pdf *.png" in captured["filter"]


def test_choose_directory(qapp, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dialogs.QFileDialog, "getExistingDirectory", staticmethod(lambda *a: str(tmp_path)))
    assert dialogs.choose_directory(None, tmp_path) == tmp_path
    monkeypatch.setattr(dialogs.QFileDialog, "getExistingDirectory", staticmethod(lambda *a: ""))
    assert dialogs.choose_directory(None, tmp_path) is None


def test_input_dialogs(qapp, monkeypatch):
    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(lambda *a: ("hi", True)))
    assert dialogs.ask_text(None, "t", "p") == "hi"
    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(lambda *a: ("hi", False)))
    assert dialogs.ask_text(None, "t", "p") is None
    monkeypatch.setattr(dialogs.QInputDialog, "getInt", staticmethod(lambda *a: (7, True)))
    assert dialogs.ask_int(None, "t", "p", 1, 1, 9) == 7
    monkeypatch.setattr(dialogs.QInputDialog, "getInt", staticmethod(lambda *a: (7, False)))
    assert dialogs.ask_int(None, "t", "p", 1, 1, 9) is None
    monkeypatch.setattr(dialogs.QInputDialog, "getItem", staticmethod(lambda *a: ("b", True)))
    assert dialogs.ask_choice(None, "t", "p", ["a", "b"]) == "b"
    monkeypatch.setattr(dialogs.QInputDialog, "getItem", staticmethod(lambda *a: ("b", False)))
    assert dialogs.ask_choice(None, "t", "p", ["a", "b"]) is None


def test_worker_run_body_directly(qapp):
    """QThread bodies are not traced by coverage; call run() inline once."""
    seen: list[str] = []

    def boom():
        raise ValueError("inline")

    w = Worker(boom)
    w.failed.connect(seen.append)
    w.run()
    assert seen and "inline" in seen[0]


# --- theme and assets -------------------------------------------------------
def test_icon_asset_is_a_valid_ico(qapp):
    data = theme.asset_path("icon.ico").read_bytes()
    assert data[:4] == b"\x00\x00\x01\x00"  # ICO header: reserved=0, type=1 (icon)


def test_apply_scheme_uses_the_winui_surface_colours(qapp):
    # The exact values pin the palette to WinUI's SolidBackgroundFillColorBase.
    theme.apply_scheme("Dark")
    assert qapp.palette().window().color().name() == "#202020"
    assert qapp.palette().brightText().color().name() == "#ff99a4"  # SystemFillColorCritical
    theme.apply_scheme("Light")
    assert qapp.palette().window().color().name() == "#f3f3f3"
    theme.apply_scheme("System")  # no OS scheme offscreen, so light
    assert qapp.palette().window().color().name() == "#f3f3f3"


def test_stylesheet_leaves_controls_to_the_native_style(qapp):
    native, fusion = theme.stylesheet("windows11"), theme.stylesheet("fusion")
    assert "QGroupBox" in native and "QPushButton" not in native
    assert "QGroupBox" in fusion and "QPushButton" in fusion


# --- PlaceDialog ------------------------------------------------------------
def test_place_dialog_text_mode(qapp, make_pdf):
    dialog = PlaceDialog(None, make_pdf("a.pdf", 3), "text")
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()  # nothing placed yet
    dialog.preview.clicked.emit(72.0, 144.0)
    assert not ok.isEnabled()  # a point without text is still incomplete
    dialog.text.setText("PAID")
    assert ok.isEnabled() and "25, 51 mm" in dialog.position.text()
    text, point, spec, font, size, rgb = dialog.params()
    assert (text, point, spec, font, size, rgb) == ("PAID", (72.0, 144.0), "1", "helv", 24, (0.0, 0.0, 0.0))
    box = dialog.box()
    assert box[0] == 72.0 and box[3] == 144.0 + 24 and box[2] > box[0]


def test_place_dialog_rejects_bad_page_spec(qapp, make_pdf):
    dialog = PlaceDialog(None, make_pdf("a.pdf", 2), "text")
    dialog.preview.clicked.emit(10.0, 10.0)
    dialog.text.setText("X")
    dialog.spec.setText("9")
    dialog._accept()
    assert dialog.result() == 0 and "outside 1-2" in dialog.error.text()  # still open
    dialog.spec.setText("")
    dialog._accept()
    assert dialog.result() == QDialog.DialogCode.Accepted  # blank = all pages


def test_place_dialog_image_mode_keeps_aspect(qapp, make_pdf, make_png, monkeypatch):
    dialog = PlaceDialog(None, make_pdf("a.pdf", 1), "image")
    png = make_png("wide.png", 40)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 20), False)  # 2:1, so the box is half as tall as wide
    pix.clear_with(80)
    pix.save(png)
    monkeypatch.setattr("pdf_helper.ui.place_dialog.QFileDialog.getOpenFileName", staticmethod(lambda *a: (str(png), "")))
    dialog.preview.clicked.emit(20.0, 30.0)
    dialog._pick_image()
    image, rect, spec = dialog.params()
    width = 50 * MM
    assert image == png and spec == "1"
    assert rect == (20.0, 30.0, 20.0 + width, 30.0 + width / 2)


def test_place_dialog_spec_follows_preview_page_until_edited(qapp, make_pdf):
    dialog = PlaceDialog(None, make_pdf("a.pdf", 3), "text")
    assert dialog.spec.text() == "1"
    dialog.page_box.setValue(3)
    assert dialog.spec.text() == "3"  # stamping the page you are looking at is the common case
    dialog.spec.setText("1-2")
    dialog.spec.textEdited.emit("1-2")  # setText alone is not a user edit; the signal is
    dialog.page_box.setValue(2)
    assert dialog.spec.text() == "1-2"  # a hand-written spec is never overwritten


def test_place_dialog_page_switch_and_unreadable_image(qapp, make_pdf, tmp_path: Path, monkeypatch):
    dialog = PlaceDialog(None, make_pdf("a.pdf", 2), "image")
    first = dialog.preview.base.size()
    dialog.page_box.setValue(2)
    assert dialog.preview.base.size() == first  # same page geometry, re-rendered without error
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    monkeypatch.setattr("pdf_helper.ui.place_dialog.QFileDialog.getOpenFileName", staticmethod(lambda *a: (str(bad), "")))
    dialog._pick_image()
    assert "cannot read broken.png" in dialog.error.text() and dialog.image.text() == ""
    monkeypatch.setattr("pdf_helper.ui.place_dialog.QFileDialog.getOpenFileName", staticmethod(lambda *a: ("", "")))
    dialog._pick_image()  # cancelled file chooser changes nothing
    assert dialog.image.text() == ""


def test_place_dialog_colour_picker(qapp, make_pdf, monkeypatch):
    dialog = PlaceDialog(None, make_pdf("a.pdf", 1), "text")
    dialog.preview.clicked.emit(10.0, 10.0)
    dialog.text.setText("X")
    monkeypatch.setattr("pdf_helper.ui.place_dialog.QColorDialog.getColor", staticmethod(lambda *a: QColor("red")))
    dialog._pick_colour()
    assert dialog.params()[5] == (1.0, 0.0, 0.0) and dialog.colour_button.text() == "#ff0000"
    monkeypatch.setattr("pdf_helper.ui.place_dialog.QColorDialog.getColor", staticmethod(lambda *a: QColor()))
    dialog._pick_colour()  # invalid colour = cancelled
    assert dialog.params()[5] == (1.0, 0.0, 0.0)


class _ClickEvent:
    """Stand-in for QMouseEvent: only position() is read."""

    def __init__(self, x: float, y: float):
        self._p = QPointF(x, y)

    def position(self) -> QPointF:
        return self._p


def test_preview_click_maps_pixels_to_points(qapp, make_pdf):
    seen: list[tuple[float, float]] = []
    preview = PagePreview()
    preview.clicked.connect(lambda x, y: seen.append((x, y)))
    preview.mousePressEvent(_ClickEvent(5, 5))  # no page loaded: must not dereference the event
    preview.draw_boxes([(1, 1, 2, 2)])  # nor paint
    assert seen == []

    png, width, _ = render_page_png(make_pdf("a.pdf", 1), 0, max_px=200)
    preview.show_page(png, width)
    scale = preview.base.width() / width
    preview.mousePressEvent(_ClickEvent(40 * scale, 90 * scale))
    assert len(seen) == 1 and abs(seen[0][0] - 40) < 0.5 and abs(seen[0][1] - 90) < 0.5

    # Past the page image (the dialog can be resized wider than the page): not a point on the page.
    preview.mousePressEvent(_ClickEvent(preview.base.width() + 10, 5))
    preview.mousePressEvent(_ClickEvent(5, preview.base.height() + 10))
    assert len(seen) == 1


# --- DragPreview / RedactDialog --------------------------------------------
def _loaded_preview(make_pdf):
    preview = DragPreview()
    png, width, _ = render_page_png(make_pdf("a.pdf", 1), 0, max_px=200)
    preview.show_page(png, width)
    return preview, preview.base.width() / width


def test_clamped_point_pulls_a_drag_back_onto_the_page(qapp, make_pdf):
    preview = PagePreview()
    assert preview.clamped_point(QPointF(5, 5)) is None  # no page loaded
    png, width, height = render_page_png(make_pdf("a.pdf", 1), 0, max_px=200)
    preview.show_page(png, width)
    x, y = preview.clamped_point(QPointF(-20, preview.base.height() + 50))
    # the pixmap is a whole number of pixels, so the bottom edge lands within a pixel of the page
    assert x == 0 and height - y < width / preview.base.width() + 1


def test_drag_preview_emits_the_rectangle(qapp, make_pdf):
    preview, scale = _loaded_preview(make_pdf)
    seen: list[tuple] = []
    preview.dragged.connect(lambda *box: seen.append(box))
    # dragged bottom-right to top-left: the rectangle comes back the right way round
    preview.mousePressEvent(_ClickEvent(120 * scale, 140 * scale))
    preview.mouseMoveEvent(_ClickEvent(60 * scale, 40 * scale))
    preview.mouseReleaseEvent(_ClickEvent(60 * scale, 40 * scale))
    assert len(seen) == 1 and all(abs(a - b) < 0.5 for a, b in zip(seen[0], (60, 40, 120, 140)))


def test_drag_preview_ignores_a_click(qapp, make_pdf):
    preview, scale = _loaded_preview(make_pdf)
    seen: list[tuple] = []
    preview.dragged.connect(lambda *box: seen.append(box))
    preview.mousePressEvent(_ClickEvent(50 * scale, 50 * scale))
    preview.mouseReleaseEvent(_ClickEvent(51 * scale, 51 * scale))  # under MIN_SIDE: a click, not a box
    preview.mouseMoveEvent(_ClickEvent(80 * scale, 80 * scale))  # no drag in progress
    assert seen == []


def test_drag_preview_ignores_a_press_past_the_page(qapp, make_pdf):
    preview, scale = _loaded_preview(make_pdf)
    seen: list[tuple] = []
    preview.dragged.connect(lambda *box: seen.append(box))
    preview.mousePressEvent(_ClickEvent(preview.base.width() + 10, 5))
    preview.mouseReleaseEvent(_ClickEvent(50 * scale, 50 * scale))
    assert seen == []


def test_redact_dialog_collects_boxes_per_page(qapp, make_pdf):
    dialog = RedactDialog(None, make_pdf("a.pdf", 3))
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()

    dialog.preview.dragged.emit(10, 10, 100, 100)
    dialog.preview.dragged.emit(20, 20, 60, 60)
    assert ok.isEnabled() and dialog.count.text() == "2 on this page, 2 in all"

    dialog.page_box.setValue(3)
    assert dialog.count.text() == "0 on this page, 2 in all"
    dialog.preview.dragged.emit(30, 30, 90, 90)
    boxes, needle, case_sensitive = dialog.params()
    assert sorted(boxes) == [0, 2] and len(boxes[0]) == 2 and needle == "" and case_sensitive is False


def test_redact_dialog_undo_and_clear(qapp, make_pdf):
    dialog = RedactDialog(None, make_pdf("a.pdf", 1))
    dialog._undo()  # nothing to undo yet
    dialog.preview.dragged.emit(10, 10, 100, 100)
    dialog.preview.dragged.emit(20, 20, 60, 60)
    dialog._undo()
    assert dialog.params()[0] == {0: [(10, 10, 100, 100)]}
    dialog._clear_page()
    assert dialog.params()[0] == {} and not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_redact_dialog_text_alone_is_enough(qapp, make_pdf):
    dialog = RedactDialog(None, make_pdf("a.pdf", 1))
    dialog.find.setText("secret")
    dialog.match_case.setChecked(True)
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert dialog.params() == ({}, "secret", True)
