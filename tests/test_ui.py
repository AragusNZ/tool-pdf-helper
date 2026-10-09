"""Qt widgets and helpers, run offscreen."""

import json
from pathlib import Path

import pymupdf
from PySide6.QtCore import QMimeData, QPointF, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QSpinBox

from pdf_helper.core.edit import EDITS_EXT
from pdf_helper.core.render import render_page_png
from pdf_helper.core.stamp import MM
from pdf_helper.ui import dialogs, theme
from pdf_helper.ui.edit_dialog import EditDialog
from pdf_helper.ui.file_queue import FileQueue
from pdf_helper.ui.place_dialog import PlaceDialog
from pdf_helper.ui.preview import PagePreview
from pdf_helper.ui.redact_dialog import DragPreview, RedactDialog
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


def test_queue_skips_a_folder_it_cannot_read(qapp, monkeypatch, tmp_path: Path):
    locked = tmp_path / "locked"
    locked.mkdir()
    monkeypatch.setattr(Path, "iterdir", lambda self: (_ for _ in ()).throw(PermissionError("denied")))
    q = FileQueue()
    assert q.add_paths([locked]) == [locked] and q.paths() == []


def test_queue_dedupes_a_relative_spelling(qapp, make_pdf, monkeypatch):
    pdf = make_pdf("a.pdf", 1)
    monkeypatch.chdir(pdf.parent)
    q = FileQueue()
    q.add_paths([pdf, Path("a.pdf")])
    assert q.paths() == [pdf]


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



def test_save_path_for_another_type(qapp, monkeypatch, tmp_path: Path):
    seen = {}

    def fake(parent, title, start, filt):
        seen["title"], seen["start"], seen["filter"] = title, start, filt
        return (str(tmp_path / "out"), "")

    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", staticmethod(fake))
    assert dialogs.save_pdf_path(None, tmp_path / "x.docx", ".docx") == tmp_path / "out.docx"
    assert seen == {"title": "Save DOCX", "start": str(tmp_path / "x.docx"), "filter": "DOCX (*.docx)"}


def test_ask_output_one_file_is_a_save_dialog(qapp, monkeypatch, tmp_path: Path):
    src = tmp_path / "report.pdf"
    starts: list[str] = []
    answer = [str(tmp_path / "Final")]
    monkeypatch.setattr(
        dialogs.QFileDialog, "getSaveFileName", staticmethod(lambda p, t, start, f: (starts.append(start), (answer[0], ""))[1])
    )
    name = dialogs.ask_output(None, [src], "-small")
    assert starts == [str(tmp_path / "report-small.pdf")]  # the old automatic name is the suggestion
    assert name(src) == tmp_path / "Final.pdf"
    answer[0] = ""
    assert dialogs.ask_output(None, [src], "-small") is None


def test_ask_output_batch_is_folder_then_suffix(qapp, monkeypatch, tmp_path: Path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "a-v2.pdf").write_bytes(b"")  # taken: numbered, never overwritten
    defaults: list[str] = []

    def get_text(parent, title, prompt, mode, default):
        defaults.append(default)
        return ("-v2", True)

    monkeypatch.setattr(dialogs.QFileDialog, "getExistingDirectory", staticmethod(lambda *a: str(out)))
    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(get_text))
    name = dialogs.ask_output(None, [tmp_path / "a.pdf", tmp_path / "b.pdf"], "-small")
    assert defaults == ["-small"]
    assert name(tmp_path / "a.pdf") == out / "a-v2 (2).pdf" and name(tmp_path / "b.pdf") == out / "b-v2.pdf"


def test_ask_output_batch_cancelled_at_either_step(qapp, monkeypatch, tmp_path: Path):
    files = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    monkeypatch.setattr(dialogs.QFileDialog, "getExistingDirectory", staticmethod(lambda *a: ""))
    assert dialogs.ask_output(None, files, "-x") is None
    monkeypatch.setattr(dialogs.QFileDialog, "getExistingDirectory", staticmethod(lambda *a: str(tmp_path)))
    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(lambda *a: ("", False)))
    assert dialogs.ask_output(None, files, "-x") is None

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


def test_apply_scheme_tolerates_an_unknown_stored_value(qapp):
    theme.apply_scheme("Sepia")  # an old or hand-edited setting must not stop the app at startup


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
    assert dialog.op() == {"kind": "text", "text": "PAID", "pos": [72.0, 144.0], "pages": "1", "font": "helv", "size": 24,
                           "color": [0.0, 0.0, 0.0]}
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


def test_place_dialog_image_mode_keeps_aspect(qapp, make_pdf, make_png, monkeypatch, tmp_path: Path):
    dialog = PlaceDialog(None, make_pdf("a.pdf", 1), "image", start=tmp_path / "pictures")
    assert dialog.page_box.suffix() == " of 1"
    png = make_png("wide.png", 40)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 20), False)  # 2:1, so the box is half as tall as wide
    pix.clear_with(80)
    pix.save(png)
    opened_at: list[str] = []
    monkeypatch.setattr(
        "pdf_helper.ui.place_dialog.QFileDialog.getOpenFileName",
        staticmethod(lambda parent, title, start, filt: opened_at.append(start) or (str(png), "")),
    )
    dialog.preview.clicked.emit(20.0, 30.0)
    dialog._pick_image()
    assert opened_at == [str(tmp_path / "pictures")]  # Browse opens where asked, not beside the previewed file
    op = dialog.op()
    width = 50 * MM
    assert op["kind"] == "image" and op["image"] == str(png) and op["pages"] == "1"
    assert op["rect"] == [20.0, 30.0, 20.0 + width, 30.0 + width / 2]


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
    assert dialog.op()["color"] == [1.0, 0.0, 0.0] and dialog.colour_button.text() == "#ff0000"
    monkeypatch.setattr("pdf_helper.ui.place_dialog.QColorDialog.getColor", staticmethod(lambda *a: QColor()))
    dialog._pick_colour()  # invalid colour = cancelled
    assert dialog.op()["color"] == [1.0, 0.0, 0.0]


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


# --- EditDialog -------------------------------------------------------------
TEXT = {"kind": "text", "text": "PAID", "pos": [72.0, 144.0], "pages": "", "font": "helv", "size": 30, "color": [1, 0, 0]}
NUMBERS = {"kind": "numbers", "fmt": "Page {n}", "position": "Top left"}
WATERMARK = {"kind": "watermark", "text": "DRAFT"}
MOD = "pdf_helper.ui.edit_dialog."


def _rows(dialog: EditDialog) -> list[str]:
    return [dialog.list.item(i).text() for i in range(dialog.list.count())]


def _outlined(dialog: EditDialog) -> bool:
    return dialog.preview.pixmap().toImage() != dialog.preview.base.toImage()


def test_edit_dialog_stacks_edits_and_previews_them(qapp, make_pdf, monkeypatch):
    dialog = EditDialog(None, [make_pdf("a.pdf", 2)])
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled() and ok.text() == "Save PDF..." and dialog.current == dialog.src
    assert dialog.page_box.suffix() == " of 2"
    monkeypatch.setattr(MOD + "ask_text", lambda *a: " DRAFT ")
    dialog._add_watermark()
    monkeypatch.setattr(MOD + "ask_options", lambda *a: {"Show": "Page 1", "Position": "Top left"})
    dialog._add_numbers()
    assert dialog.status.text() == ""
    monkeypatch.setattr(MOD + "ask_options", lambda *a: {"Find": " page ", "Replace with": "leaf", "Match case": True})
    dialog._add_replace()
    assert _rows(dialog) == ['Watermark "DRAFT"', "Page numbers: Page 1, Top left", 'Replace "page" with "leaf" (match case)']
    assert dialog.status.text() == "2 replacement(s) in a.pdf"  # the count is the only sign a Find text matched
    assert ok.isEnabled() and dialog.remove.isEnabled() and dialog.current != dialog.src
    with pymupdf.open(dialog.current) as doc:  # the preview file carries every edit
        text = doc[1].get_text()
        assert "DRAFT" in text and "Page 2" in text and "leaf" in text and "page" not in text
    before = dialog.preview.base.cacheKey()
    dialog.page_box.setValue(2)
    assert dialog.preview.base.cacheKey() != before  # re-rendered from the composed file
    monkeypatch.setattr(MOD + "ask_options", lambda *a: {"Find": "zzz", "Replace with": "", "Match case": False})
    dialog._add_replace()
    assert dialog.status.text() == "2 replacement(s); 0 replacement(s) in a.pdf"


def test_edit_dialog_heading_names_the_batch(qapp, make_pdf):
    one, two = make_pdf("a.pdf", 1), make_pdf("b.pdf", 1)
    labels = [w.text() for w in EditDialog(None, [one, two]).findChildren(QLabel)]
    assert "a.pdf - edits apply to all 2 queued files" in labels
    assert "a.pdf" in [w.text() for w in EditDialog(None, [one]).findChildren(QLabel)]


def test_edit_dialog_cancelled_prompts_add_nothing(qapp, make_pdf, monkeypatch):
    dialog = EditDialog(None, [make_pdf("a.pdf", 1)])
    for answer in (None, "   "):
        monkeypatch.setattr(MOD + "ask_text", lambda *a, answer=answer: answer)
        dialog._add_watermark()
    monkeypatch.setattr(MOD + "ask_options", lambda *a: None)
    dialog._add_numbers()
    dialog._add_replace()
    monkeypatch.setattr(MOD + "ask_options", lambda *a: {"Find": "  ", "Replace with": "x", "Match case": False})
    dialog._add_replace()  # a blank Find is a cancel
    assert dialog.ops == [] and dialog.status.text() == ""


def test_edit_dialog_places_on_the_composed_page(qapp, make_pdf, make_png, monkeypatch):
    png = make_png()
    image = {"kind": "image", "image": str(png), "rect": [50.0, 50.0, 110.0, 110.0], "pages": "1"}
    opened: list = []

    class FakePlace:
        accept = True

        def __init__(self, parent, src: Path, mode: str, start: Path | None = None):
            self.src, self.mode, self.start, self.page_box = src, mode, start, QSpinBox(maximum=9)
            opened.append(self)

        def exec(self) -> bool:
            return type(self).accept

        def op(self) -> dict:
            return TEXT if self.mode == "text" else image

    monkeypatch.setattr(MOD + "PlaceDialog", FakePlace)
    dialog = EditDialog(None, [make_pdf("a.pdf", 2)])
    dialog.page_box.setValue(2)
    dialog._place("text")
    assert opened[0].src == dialog.src and opened[0].page_box.value() == 2
    composed = dialog.current
    dialog._place("image")
    assert opened[1].src == composed != dialog.src  # the second is placed on the page with the first already on it
    assert opened[1].start == dialog.src.parent  # but images are browsed from beside the real file, not the temp one
    assert _rows(dialog) == ['Text "PAID" on all pages', "Image pic.png on page 1"]
    FakePlace.accept = False
    dialog._place("text")
    assert len(dialog.ops) == 2


def test_edit_dialog_outlines_the_selected_text_or_image(qapp, make_pdf):
    dialog = EditDialog(None, [make_pdf("a.pdf", 2)])
    dialog._set([{**TEXT, "pages": "2"}, NUMBERS])
    dialog.list.setCurrentRow(1)
    assert not _outlined(dialog)  # page numbers have no single box
    dialog.list.setCurrentRow(0)
    assert not _outlined(dialog)  # the text lands on page 2, page 1 is shown
    dialog.page_box.setValue(2)
    assert _outlined(dialog)
    assert dialog._box(TEXT)[0] == 72.0 and dialog._box(TEXT)[3] == 144.0 + 30
    image = {"kind": "image", "image": "x.png", "rect": [1.0, 2.0, 3.0, 4.0], "pages": ""}
    assert dialog._box(image) == (1.0, 2.0, 3.0, 4.0) and dialog._box(None) is None


def test_edit_dialog_remove_move_and_an_edit_that_does_not_apply(qapp, make_pdf):
    dialog = EditDialog(None, [make_pdf("a.pdf", 1)])
    assert dialog._add(WATERMARK)
    assert not dialog._add({**TEXT, "pages": "4"})
    assert dialog.status.text() == 'Text "PAID" on page 4: page range \'4\' outside 1-1'  # named, and not kept
    assert dialog.ops == [WATERMARK]
    assert dialog._add(NUMBERS) and dialog._add(TEXT) and dialog.status.text() == ""
    dialog.list.setCurrentRow(0)
    dialog._move(1)
    assert _rows(dialog)[:2] == ["Page numbers: Page 1, Top left", 'Watermark "DRAFT"'] and dialog.list.currentRow() == 1
    dialog._move(-1)
    assert _rows(dialog)[0] == 'Watermark "DRAFT"' and dialog.list.currentRow() == 0
    dialog._move(-1)  # already first: nothing happens
    assert dialog.list.currentRow() == 0
    dialog._remove()
    assert _rows(dialog) == ["Page numbers: Page 1, Top left", 'Text "PAID" on all pages'] and dialog.list.currentRow() == 0
    dialog.list.setCurrentRow(1)
    dialog.delete_key.activated.emit()  # the Delete key is Remove
    assert _rows(dialog) == ["Page numbers: Page 1, Top left"]
    dialog._remove()
    assert dialog.ops == [] and dialog.current == dialog.src
    assert not dialog.remove.isEnabled() and not dialog.up.isEnabled() and not dialog.down.isEnabled()
    dialog._remove()  # nothing selected: nothing happens
    assert dialog.ops == []


def test_edit_dialog_saves_and_loads_edits(qapp, make_pdf, tmp_path: Path, monkeypatch):
    dialog = EditDialog(None, [make_pdf("a.pdf", 1)])
    dialog._set([WATERMARK, NUMBERS])
    typed = tmp_path / "recipe"  # no suffix typed: it is added
    monkeypatch.setattr(MOD + "QFileDialog.getSaveFileName", staticmethod(lambda *a: (str(typed), "")))
    dialog._save_edits()
    saved = tmp_path / f"recipe{EDITS_EXT}"
    assert json.loads(saved.read_text()) == [WATERMARK, NUMBERS]
    other = EditDialog(None, [make_pdf("b.pdf", 2)])
    monkeypatch.setattr(MOD + "QFileDialog.getOpenFileName", staticmethod(lambda *a: (str(saved), "")))
    other._load_edits()
    assert other.ops == [WATERMARK, NUMBERS] and other.current != other.src
    monkeypatch.setattr(MOD + "QFileDialog.getSaveFileName", staticmethod(lambda *a: ("", "")))
    monkeypatch.setattr(MOD + "QFileDialog.getOpenFileName", staticmethod(lambda *a: ("", "")))
    saved.unlink()
    dialog._save_edits()  # cancelled chooser writes nothing
    other._load_edits()  # and loads nothing
    assert not saved.exists() and len(other.ops) == 2


def test_edit_dialog_load_stops_at_the_first_bad_edit(qapp, make_pdf, tmp_path: Path, monkeypatch):
    path = tmp_path / f"x{EDITS_EXT}"
    path.write_text(json.dumps([WATERMARK, {**TEXT, "pages": "9"}, NUMBERS]))
    monkeypatch.setattr(MOD + "QFileDialog.getOpenFileName", staticmethod(lambda *a: (str(path), "")))
    dialog = EditDialog(None, [make_pdf("a.pdf", 1)])
    dialog._load_edits()
    assert dialog.ops == [WATERMARK] and dialog.status.text() == 'Text "PAID" on page 9: page range \'9\' outside 1-1'
    path.write_text("not json")
    dialog._load_edits()
    assert dialog.status.text() == f"x{EDITS_EXT} is not an edits file" and dialog.ops == [WATERMARK]


def test_edit_dialog_save_pdf_asks_where_and_stays_open_on_cancel(qapp, make_pdf, tmp_path: Path, monkeypatch):
    dialog = EditDialog(None, [make_pdf("a.pdf", 1), make_pdf("b.pdf", 1)])
    dialog._set([WATERMARK])
    tmp = Path(dialog._tmp.name)
    assert any(tmp.iterdir())
    accepted: list[int] = []
    dialog.accepted.connect(lambda: accepted.append(1))
    asked: list = []
    monkeypatch.setattr(MOD + "ask_output", lambda parent, files, suffix: asked.append((files, suffix)))  # returns None
    dialog.accept()
    assert accepted == [] and dialog.namer is None and dialog.ops == [WATERMARK]  # cancelled Save: still editing
    assert asked == [(dialog.files, "-edited")]
    monkeypatch.setattr(MOD + "ask_output", lambda *a: (lambda src: tmp_path / f"{src.stem}-edited.pdf"))
    dialog.accept()
    assert accepted == [1] and dialog.namer(dialog.src) == tmp_path / "a-edited.pdf"
    assert not tmp.exists()  # the preview files go with the dialog


def test_edit_dialog_cancel_asks_only_when_edits_are_pending(qapp, make_pdf, monkeypatch):
    dialog = EditDialog(None, [make_pdf("a.pdf", 1)])
    rejected: list[int] = []
    dialog.rejected.connect(lambda: rejected.append(1))
    dialog.reject()
    assert rejected == [1]  # nothing to lose, no question
    dialog = EditDialog(None, [make_pdf("b.pdf", 1)])  # a finished dialog is done with; start another
    dialog.rejected.connect(lambda: rejected.append(1))
    dialog._set([WATERMARK])
    tmp = Path(dialog._tmp.name)
    monkeypatch.setattr(MOD + "QMessageBox.question", staticmethod(lambda *a: QMessageBox.StandardButton.No))
    dialog.reject()
    assert rejected == [1]  # kept open
    monkeypatch.setattr(MOD + "QMessageBox.question", staticmethod(lambda *a: QMessageBox.StandardButton.Yes))
    dialog.reject()
    assert rejected == [1, 1] and not tmp.exists()


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


def test_redact_dialog_ignores_a_blank_phrase(qapp, make_pdf):
    """A phrase of spaces would black out every gap between words, so it does not count as input."""
    dialog = RedactDialog(None, make_pdf("a.pdf", 1))
    dialog.find.setText("   ")
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert dialog.params() == ({}, "", False)


def test_redact_dialog_text_alone_is_enough(qapp, make_pdf):
    dialog = RedactDialog(None, make_pdf("a.pdf", 1))
    dialog.find.setText(" secret ")
    dialog.match_case.setChecked(True)
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert dialog.params() == ({}, "secret", True)  # trimmed


def test_ask_password_rejects_blank_and_mismatch(qapp, monkeypatch):
    answers = iter([("", True), ("a", True), ("b", True), ("a", True), ("a", True)])
    prompts: list[str] = []

    def get_text(parent, title, prompt, echo):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(get_text))
    assert dialogs.ask_password(None, "t", confirm=True) == "a"
    assert "blank" in prompts[1] and "did not match" in prompts[3]
    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(lambda *a: ("x", True)))
    assert dialogs.ask_password(None, "t", confirm=False) == "x"
    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(lambda *a: ("", False)))
    assert dialogs.ask_password(None, "t", confirm=True) is None
    answers = iter([("a", True), ("", False)])
    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(lambda *a: next(answers)))
    assert dialogs.ask_password(None, "t", confirm=True) is None  # cancelled on the second ask


def test_ask_fields(qapp, monkeypatch):
    from PySide6.QtWidgets import QLineEdit

    def accept(self):
        self.findChildren(QLineEdit)[1].setText("Bo")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept)
    assert dialogs.ask_fields(None, "t", {"Title": "T", "Author": ""}) == {"Title": "T", "Author": "Bo"}
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert dialogs.ask_fields(None, "t", {"Title": "T"}) is None


def test_ask_options(qapp, monkeypatch):
    from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit

    def accept(self):
        self.findChildren(QCheckBox)[0].setChecked(True)
        self.findChildren(QComboBox)[0].setCurrentIndex(1)
        self.findChildren(QLineEdit)[0].setText("Bo")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept)
    fields = {"Loud": False, "Size": ["S", "M"], "Fast": True, "Name": "Al"}
    assert dialogs.ask_options(None, "t", fields) == {"Loud": True, "Size": "M", "Fast": True, "Name": "Bo"}
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert dialogs.ask_options(None, "t", fields) is None


def test_ask_options_colour_presets_and_picker(qapp, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog, QComboBox

    fields = {"Ink": {"Red": "#cc0000", "Blue": "#0000ff"}}

    def pick_preset(self):
        self.findChildren(QComboBox)[0].setCurrentIndex(1)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", pick_preset)
    assert dialogs.ask_options(None, "t", fields) == {"Ink": "#0000ff"}

    picked = [QColor("#123456"), QColor()]  # a choice, then a cancelled dialog

    def pick_custom(self):
        combo = self.findChildren(QComboBox)[0]
        combo.activated.emit(1)  # a preset: remembered as the fallback
        combo.activated.emit(combo.count() - 1)  # "Pick colour..." -> custom colour inserted and selected
        assert combo.currentText() == "Custom (#123456)"
        combo.activated.emit(combo.count() - 1)  # cancelled -> stays on the custom colour
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: picked.pop(0)))
    monkeypatch.setattr(QDialog, "exec", pick_custom)
    assert dialogs.ask_options(None, "t", fields) == {"Ink": "#123456"}
