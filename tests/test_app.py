"""MainWindow wiring: buttons follow the queue, features run on the worker, errors reach the log."""

from pathlib import Path

import pytest
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import QPushButton

from pdf_helper import app as app_module
from pdf_helper.app import MainWindow
from pdf_helper.features import FEATURES
from pdf_helper.features.base import Feature, FeatureContext, each_file


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
    assert w.queue.paths() == [pdf] and "skipped x.zip" in w.log_view.toPlainText()


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


def test_delete_key_removes_the_selected_files(qapp, make_pdf):
    w = MainWindow()
    a, b = make_pdf("a.pdf", 1), make_pdf("b.pdf", 1)
    w.queue.add_paths([a, b])
    w.queue.item(0).setSelected(True)
    shortcut = next(s for s in w.queue.children() if isinstance(s, QShortcut))
    shortcut.activated.emit()
    assert w.queue.paths() == [b]


def test_add_files_remembers_the_folder(qapp, monkeypatch, make_pdf):
    pdf = make_pdf("a.pdf", 1)
    starts: list[str] = []

    def picker(parent, exts, start=""):
        starts.append(start)
        return [pdf] if not starts[:-1] else []

    monkeypatch.setattr(app_module, "open_file_paths", picker)
    app_module.settings().remove("last_dir")
    try:
        w = MainWindow()
        w._add_files()  # nothing remembered yet
        w._add_files()  # now it opens where the first batch came from
        assert starts == ["", str(pdf.parent)]
    finally:
        app_module.settings().remove("last_dir")



def test_actions_are_split_into_tabs(qapp):
    w = MainWindow()
    groups: dict[str, list[str]] = {}
    for feature in FEATURES:
        groups.setdefault(feature.group, []).append(feature.label)
    assert [w.tabs.tabText(i) for i in range(w.tabs.count())] == list(groups)
    # every registry entry still has exactly one button, and it sits on its own tab
    assert [f.label for f, _ in w.feature_buttons] == [label for labels in groups.values() for label in labels]
    for i, labels in enumerate(groups.values()):
        assert [b.text() for b in w.tabs.widget(i).findChildren(QPushButton)] == labels


def test_a_group_named_twice_lands_on_one_tab(qapp):
    """Registry order decides tab order; a stray out-of-order entry must not open a second tab."""
    runner = Feature(label="X", run=lambda ctx, params: None, group="Pages")
    other = Feature(label="Y", run=lambda ctx, params: None, group="Convert")
    third = Feature(label="Z", run=lambda ctx, params: None, group="Pages")
    w = _window(qapp, [runner, other, third])
    assert [w.tabs.tabText(i) for i in range(w.tabs.count())] == ["Pages", "Convert"]
    assert [b.text() for b in w.tabs.widget(0).findChildren(QPushButton)] == ["X", "Z"]


def _check(w: MainWindow, qapp, manual: bool) -> None:
    w._check_updates(manual=manual)
    worker = w._update_worker
    assert worker is not None and worker.wait(10000)
    qapp.processEvents()


def _stub_update(monkeypatch, latest):
    """Stub the network and every dialog; return what the window asked for."""
    seen: dict = {"opened": [], "info": []}

    def fetch():
        if isinstance(latest, Exception):
            raise latest
        return latest

    monkeypatch.setattr(app_module, "latest_version", fetch)
    monkeypatch.setattr(app_module.QMessageBox, "question", lambda *a: app_module.QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(app_module.QMessageBox, "information", lambda *a: seen["info"].append(a[-1]))
    monkeypatch.setattr(app_module.QDesktopServices, "openUrl", lambda url: seen["opened"].append(url.toString()))
    return seen


def test_newer_release_opens_the_download_page(qapp, monkeypatch):
    seen = _stub_update(monkeypatch, "999.0.0")
    w = MainWindow()
    _check(w, qapp, manual=False)
    assert seen["opened"] == [app_module.RELEASES_URL] and w._update_worker is None


def test_up_to_date_speaks_only_when_asked(qapp, monkeypatch):
    seen = _stub_update(monkeypatch, app_module.__version__)
    w = MainWindow()
    _check(w, qapp, manual=False)
    assert seen["info"] == []
    _check(w, qapp, manual=True)
    assert len(seen["info"]) == 1 and "up to date" in seen["info"][0] and seen["opened"] == []


def test_update_failure_logged_only_when_asked(qapp, monkeypatch):
    _stub_update(monkeypatch, OSError("offline"))
    w = MainWindow()
    _check(w, qapp, manual=False)
    assert "update check failed" not in w.log_view.toPlainText()
    _check(w, qapp, manual=True)
    assert "ERROR: update check failed: offline" in w.log_view.toPlainText()


def test_startup_check_toggle_is_remembered(qapp):
    app_module.settings().remove("check_updates")
    try:
        w = MainWindow()
        assert w.startup_check.isChecked()  # on by default
        w.startup_check.setChecked(False)
        assert not app_module.check_on_startup() and not MainWindow().startup_check.isChecked()
    finally:
        app_module.settings().remove("check_updates")


def test_close_waits_for_a_running_update_check(qapp, monkeypatch):
    import threading
    import time

    from PySide6.QtGui import QCloseEvent

    release = threading.Event()
    calls: list[int] = []

    def slow():
        calls.append(1)
        release.wait(5)
        return app_module.__version__

    _stub_update(monkeypatch, None)
    monkeypatch.setattr(app_module, "latest_version", slow)
    w = MainWindow()
    w._check_updates(manual=False)
    worker = w._update_worker
    w._check_updates(manual=True)  # second click while one is in flight is ignored
    assert w._update_worker is worker
    threading.Timer(0.2, release.set).start()
    started = time.monotonic()
    ev = QCloseEvent()
    w.closeEvent(ev)
    assert ev.isAccepted() and worker.isFinished() and time.monotonic() - started >= 0.1 and calls == [1]
    qapp.processEvents()


@pytest.fixture(autouse=True)
def _forget_geometry():
    """An accepted close saves the window geometry; keep test runs out of the real settings."""
    yield
    app_module.settings().remove("geometry")


def test_cancel_stops_between_files(qapp, tmp_path: Path):
    import threading

    gate, started = threading.Event(), threading.Event()
    seen: list[str] = []

    def one(src: Path) -> Path:
        seen.append(src.name)
        started.set()
        gate.wait(5)  # hold the first file until the cancel is in
        return src

    feat = Feature(label="T", run=lambda ctx, p: each_file(ctx, one), exts=None)
    files = []
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text("x")
        files.append(tmp_path / name)
    w = _window(qapp, [feat])
    w.queue.add_paths(files)
    w._run_feature(feat)
    assert not w.cancel_button.isHidden()  # in the status bar while busy
    assert started.wait(5)
    w.cancel_button.click()
    assert not w.cancel_button.isEnabled() and w._worker.isInterruptionRequested()
    gate.set()
    _wait(w, qapp)
    assert w.cancel_button.isHidden()
    text = w.log_view.toPlainText()
    assert seen == ["a.txt"] and "cancelled: 1 of 3 file(s) done" in text
    assert w.progress.maximum() == 3 and w.progress.value() == 1 and w.progress.text() == "1 of 3"


def test_open_output_folder_after_a_job(qapp, monkeypatch, make_pdf, tmp_path: Path):
    opened: list[str] = []
    monkeypatch.setattr(app_module.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    out = tmp_path / "out" / "x.pdf"
    out.parent.mkdir()
    out.write_bytes(b"")
    feat = Feature(label="T", run=lambda ctx, p: ctx.outputs.append(out))
    w = _window(qapp, [feat])
    assert not w.open_output.isEnabled()
    w.queue.add_paths([make_pdf("a.pdf", 1)])
    w._run_feature(feat)
    _wait(w, qapp)
    assert w.open_output.isEnabled()
    w.open_output.click()
    assert [Path(o) for o in opened] == [out.parent]


def test_output_folder_can_be_the_output_itself(qapp, make_pdf, tmp_path: Path):
    feat = Feature(label="T", run=lambda ctx, p: ctx.outputs.append(tmp_path))
    w = _window(qapp, [feat])
    w.queue.add_paths([make_pdf("a.pdf", 1)])
    w._run_feature(feat)
    _wait(w, qapp)
    assert w._output_dir == tmp_path


def test_window_geometry_survives_a_restart(qapp):
    from PySide6.QtGui import QCloseEvent

    w = MainWindow()
    w.setGeometry(40, 50, 700, 520)  # inside the offscreen screen, which clamps anything larger
    w.closeEvent(QCloseEvent())
    assert app_module.settings().value("geometry")
    assert MainWindow().size() == w.size()
