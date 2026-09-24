"""End to end: real features driven through MainWindow, queue -> prepare -> worker -> files on disk.

The unit tests call feature.run() directly; these go through the window, so a break in the wiring
between the queue, the button gating, the dialogs and the worker thread shows up here.
"""

import logging
import logging.handlers
from pathlib import Path

import pymupdf
import pytest

from pdf_helper import app as app_module
from pdf_helper.app import MainWindow
from pdf_helper.core.pdf import page_count
from pdf_helper.core.convert import IMAGE_SIZE
from pdf_helper.features import create_pdf, merge, redact, split, to_images, watermark


def _run(window: MainWindow, label: str, qapp) -> str:
    feature, button = next(pair for pair in window.feature_buttons if pair[0].label == label)
    assert button.isEnabled(), f"{label} not enabled for the queue"
    button.click()
    worker = window._worker
    assert worker is not None and worker.wait(30000)
    qapp.processEvents()
    return window.log_view.toPlainText()


def test_merge_pipeline(qapp, make_pdf, make_png, tmp_path: Path, monkeypatch):
    out = tmp_path / "merged.pdf"
    monkeypatch.setattr(merge, "save_pdf_path", lambda *a: out)
    monkeypatch.setattr(create_pdf, "ask_choice", lambda *a: IMAGE_SIZE)
    w = MainWindow()
    w.queue.add_paths([make_pdf("a.pdf", 2), make_png(), make_pdf("b.pdf", 1)])

    text = _run(w, "Merge to one PDF", qapp)

    assert page_count(out) == 4
    assert "merged 3 files" in text and text.rstrip().endswith("done")


def test_watermark_pipeline_whole_queue(qapp, make_pdf, tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "stamped"
    out_dir.mkdir()
    monkeypatch.setattr(watermark, "ask_text", lambda *a: "DRAFT")
    monkeypatch.setattr(watermark, "choose_directory", lambda *a: out_dir)
    w = MainWindow()
    w.queue.add_paths([make_pdf("a.pdf", 1), make_pdf("b.pdf", 2)])

    text = _run(w, "Watermark", qapp)

    assert sorted(p.name for p in out_dir.glob("*.pdf")) == ["a-stamped.pdf", "b-stamped.pdf"]
    assert "ERROR" not in text and text.rstrip().endswith("done")


def test_to_images_pipeline(qapp, make_pdf, tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "png"
    monkeypatch.setattr(to_images, "ask_int", lambda *a: 72)
    monkeypatch.setattr(to_images, "choose_directory", lambda *a: out_dir)
    w = MainWindow()
    w.queue.add_paths([make_pdf("a.pdf", 2)])

    _run(w, "PDF to images", qapp)

    assert len(list(out_dir.glob("*.png"))) == 2


def test_pipeline_reports_bad_file_and_keeps_going(qapp, make_pdf, tmp_path: Path, monkeypatch):
    """One unreadable PDF must not stop the rest of the queue, and must reach the log as an ERROR."""
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.4 not really a pdf")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(split, "ask_int", lambda *a: 1)
    monkeypatch.setattr(split, "choose_directory", lambda *a: out_dir)
    w = MainWindow()
    w.queue.add_paths([bad, make_pdf("good.pdf", 2)])

    text = _run(w, "Split", qapp)

    assert len(list(out_dir.glob("good*.pdf"))) == 2
    assert "ERROR: broken.pdf" in text and "1 of 2 file(s) failed" in text
    assert w._worker is None  # window returns to idle even after a failing batch


def test_pipeline_queue_removal_regates_buttons(qapp, make_pdf, make_png):
    w = MainWindow()
    pdf, png = make_pdf("a.pdf", 1), make_png()
    w.queue.add_paths([pdf, png])
    labels = {f.label for f, b in w.feature_buttons if b.isEnabled()}
    assert labels == {"Create PDF(s)", "Merge to one PDF"}  # a PNG in the queue gates the PDF-only ones

    w.queue.setCurrentRow(1)
    w.queue.remove_selected()

    assert w.queue.paths() == [pdf]
    assert "Watermark" in {f.label for f, b in w.feature_buttons if b.isEnabled()}


@pytest.mark.parametrize("theme, applied", [("System", True), ("Dark", False)])
def test_system_theme_follow(monkeypatch, qapp, theme, applied):
    seen = []
    monkeypatch.setattr(app_module, "apply_scheme", lambda name: seen.append(name))
    app_module.settings().setValue("theme", theme)
    try:
        app_module._follow_system_scheme(None)
    finally:
        app_module.settings().remove("theme")
    assert bool(seen) is applied


def test_excepthook_logs_and_shows_dialog(monkeypatch, qapp, caplog):
    shown = []
    monkeypatch.setattr(app_module.QMessageBox, "critical", lambda *a: shown.append(a))
    with caplog.at_level("CRITICAL", logger="pdf_helper"):
        app_module._excepthook(ValueError, ValueError("boom"), None)
    assert shown and "boom" in shown[0][2] and "unhandled exception" in caplog.text


def test_main_builds_and_shows_the_window(monkeypatch, qapp, make_pdf):
    """The exe entry point: everything main() touches must exist (icon, style, theme, window).

    Files named on the command line (Send To, "Open with") land in the queue.
    """
    shown = []
    pdf = make_pdf("a.pdf", 1)
    monkeypatch.setattr(app_module.QApplication, "arguments", staticmethod(lambda: ["exe", str(pdf), "missing.pdf"]))
    timers: list[int] = []  # recorded, never armed: a live timer would hit the network in a later test
    monkeypatch.setattr(app_module, "check_on_startup", lambda: True)
    monkeypatch.setattr(app_module.QTimer, "singleShot", staticmethod(lambda ms, fn: timers.append(ms)))
    logging_setup: dict = {}
    monkeypatch.setattr(app_module.logging, "basicConfig", lambda **kw: logging_setup.update(kw))
    monkeypatch.setattr(app_module.QApplication, "__new__", lambda cls, argv: qapp)
    monkeypatch.setattr(app_module.QApplication, "__init__", lambda self, argv: None)
    monkeypatch.setattr(app_module.QApplication, "exec", lambda self: 0)
    monkeypatch.setattr(app_module.MainWindow, "show", lambda self: shown.append(self))
    with pytest.raises(SystemExit) as exc:
        app_module.main()
    assert exc.value.code == 0 and len(shown) == 1
    assert timers == [1500]  # the startup update check is scheduled
    assert shown[0].queue.paths() == [pdf] and "skipped missing.pdf" in shown[0].log_view.toPlainText()
    handler = logging_setup["handlers"][0]  # the log file cannot grow forever
    assert isinstance(handler, logging.handlers.RotatingFileHandler) and handler.maxBytes == 1_000_000


def test_theme_menu_and_about(qapp, monkeypatch):
    applied, about = [], []
    monkeypatch.setattr(app_module, "apply_scheme", lambda name: applied.append(name))
    monkeypatch.setattr(app_module.QMessageBox, "about", lambda *a: about.append(a))
    w = MainWindow()
    try:
        w._set_theme("Dark")
        assert applied == ["Dark"] and app_module.settings().value("theme") == "Dark"
    finally:
        app_module.settings().remove("theme")
    w._about()
    assert about and "PDF Helper" in about[0][2]


def test_redact_pipeline(qapp, make_pdf, tmp_path: Path, monkeypatch):
    """The dialog runs on the UI thread and the removal on the worker: check the whole chain once."""
    out_dir = tmp_path / "clean"
    out_dir.mkdir()

    class _Dialog:
        def __init__(self, parent, src: Path):
            self.src = src

        def exec(self) -> bool:
            return True

        def params(self) -> tuple:
            return ({0: [(60.0, 60.0, 200.0, 80.0)]}, "page 2", False)

    monkeypatch.setattr(redact, "RedactDialog", _Dialog)
    monkeypatch.setattr(redact, "choose_directory", lambda *a: out_dir)
    w = MainWindow()
    w.queue.add_paths([make_pdf("a.pdf", 2), make_pdf("b.pdf", 1)])

    text = _run(w, "Redact", qapp)

    assert sorted(p.name for p in out_dir.glob("*.pdf")) == ["a-redacted.pdf", "b-redacted.pdf"]
    with pymupdf.open(out_dir / "a-redacted.pdf") as doc:
        # the box took all of page 1; the phrase took "page 2" off page 2 and left the rest
        assert doc[0].get_text().strip() == "" and doc[1].get_text().strip() == "a.pdf"
    assert "ERROR" not in text and text.rstrip().endswith("done")
