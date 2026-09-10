"""Qt widgets and helpers, run offscreen."""

from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl

from pdf_helper.ui import dialogs
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
