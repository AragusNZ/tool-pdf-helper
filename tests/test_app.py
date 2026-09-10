"""MainWindow wiring: buttons follow the queue, features run on the worker, errors reach the log."""

from pathlib import Path

from pdf_helper import app as app_module
from pdf_helper.app import MainWindow
from pdf_helper.features import FEATURES
from pdf_helper.features.base import Feature, FeatureContext


def _wait(window: MainWindow, qapp) -> None:
    worker = window._worker
    assert worker is not None and worker.wait(10000)
    qapp.processEvents()


def _window(qapp, features):
    # Swap the registry the window reads, so tests control which buttons exist.
    orig = app_module.FEATURES
    app_module.FEATURES = features
    try:
        return MainWindow()
    finally:
        app_module.FEATURES = orig


def test_buttons_match_registry_and_queue(qapp, make_pdf, make_png):
    w = MainWindow()
    assert [f.label for f, _ in w.feature_buttons] == [f.label for f in FEATURES]
    assert not any(b.isEnabled() for _, b in w.feature_buttons)
    w.queue.add_paths([make_pdf("a.pdf", 1)])
    enabled = {f.label for f, b in w.feature_buttons if b.isEnabled()}
    assert "Extract pages" in enabled and "Merge to one PDF" not in enabled
    w.queue.add_paths([make_png()])
    enabled = {f.label for f, b in w.feature_buttons if b.isEnabled()}
    assert enabled == {"Create PDF(s)", "Merge to one PDF"}


def test_add_files_reports_skipped(qapp, monkeypatch, make_pdf, tmp_path: Path):
    bad = tmp_path / "x.zip"
    bad.write_bytes(b"")
    pdf = make_pdf("a.pdf", 1)
    monkeypatch.setattr(app_module, "open_file_paths", lambda *a: [pdf, bad])
    w = MainWindow()
    w._add_files()
    assert w.queue.paths() == [pdf] and "skipped unsupported file x.zip" in w.log_view.toPlainText()


def test_feature_runs_on_worker_and_logs(qapp, make_pdf):
    seen: dict = {}

    def run(ctx: FeatureContext, params) -> None:
        seen["files"], seen["params"], seen["parent"] = ctx.files, params, ctx.parent
        ctx.log("from worker")

    feat = Feature(label="T", prepare=lambda ctx: {"p": 1}, run=run)
    w = _window(qapp, [feat])
    w.queue.add_paths([make_pdf("a.pdf", 1)])
    button = w.feature_buttons[0][1]
    assert button.isEnabled()
    w._run_feature(feat)
    assert not button.isEnabled()  # disabled while busy
    _wait(w, qapp)
    text = w.log_view.toPlainText()
    assert seen["params"] == {"p": 1} and seen["parent"] is None and len(seen["files"]) == 1
    assert "--- T ---" in text and "from worker" in text and text.rstrip().endswith("done")
    assert w._worker is None and button.isEnabled()


def test_feature_cancelled_in_prepare(qapp, make_pdf):
    feat = Feature(label="T", prepare=lambda ctx: None, run=lambda ctx, p: None)
    w = _window(qapp, [feat])
    w.queue.add_paths([make_pdf("a.pdf", 1)])
    w._run_feature(feat)
    assert w._worker is None and "T: cancelled" in w.log_view.toPlainText()


def test_feature_error_reaches_log(qapp, make_pdf):
    def run(ctx, params):
        raise RuntimeError("bad thing")

    feat = Feature(label="T", run=run)
    w = _window(qapp, [feat])
    w.queue.add_paths([make_pdf("a.pdf", 1)])
    w._run_feature(feat)
    _wait(w, qapp)
    assert "ERROR: bad thing" in w.log_view.toPlainText()


def test_prepare_error_reaches_log_without_worker(qapp, make_pdf):
    def prepare(ctx):
        raise ValueError("cannot open")

    feat = Feature(label="T", prepare=prepare, run=lambda ctx, p: None)
    w = _window(qapp, [feat])
    w.queue.add_paths([make_pdf("a.pdf", 1)])
    w._run_feature(feat)
    assert w._worker is None and "ERROR: T: cannot open" in w.log_view.toPlainText()


def test_close_refused_while_busy(qapp, make_pdf):
    from PySide6.QtGui import QCloseEvent

    feat = Feature(label="T", run=lambda ctx, p: None)
    w = _window(qapp, [feat])
    w.queue.add_paths([make_pdf("a.pdf", 1)])
    w._run_feature(feat)
    ev = QCloseEvent()
    w.closeEvent(ev)
    assert not ev.isAccepted() and "still working" in w.log_view.toPlainText()
    _wait(w, qapp)
    ev = QCloseEvent()
    w.closeEvent(ev)
    assert ev.isAccepted()
