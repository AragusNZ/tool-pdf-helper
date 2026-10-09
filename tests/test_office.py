"""Office conversion: COM branches via fake win32com, fallback order, failure messages."""

import subprocess
import sys
import types
from pathlib import Path

import pytest

from pdf_helper.core import office
from pdf_helper.core.office import ConversionError, find_libreoffice, office_to_pdf


class _Fake:
    """Records attribute sets and calls along any chain: app.Documents.Open(...) -> doc.Close(...)."""

    def __init__(self, calls: list, name: str = ""):
        object.__setattr__(self, "calls", calls)
        object.__setattr__(self, "name", name)

    def __getattr__(self, name):
        return _Fake(self.calls, name)

    def __call__(self, *args, **kwargs):
        self.calls.append((self.name, args, kwargs))
        return _Fake(self.calls)

    def __setattr__(self, name, value):
        self.calls.append(("set", name, value))


@pytest.fixture
def fake_com(monkeypatch):
    """Install fake pythoncom + win32com.client and force the COM path on."""
    calls: list = []
    progids: list[str] = []

    def dispatch(progid):
        progids.append(progid)
        return _Fake(calls)

    win32com = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")
    client.DispatchEx = dispatch
    win32com.client = client
    pythoncom = types.ModuleType("pythoncom")
    pythoncom.CoInitialize = lambda: calls.append(("CoInitialize",))
    pythoncom.CoUninitialize = lambda: calls.append(("CoUninitialize",))
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setattr(office, "_com_available", lambda: True)
    return calls, progids


def _names(calls):
    return [c[0] for c in calls]


@pytest.mark.parametrize(
    "ext, progid, export",
    [(".docx", "Word.Application", "ExportAsFixedFormat"), (".xlsx", "Excel.Application", "ExportAsFixedFormat"),
     (".pptx", "PowerPoint.Application", "SaveAs")],
)
def test_com_branches(fake_com, tmp_path: Path, ext, progid, export):
    calls, progids = fake_com
    src, out = tmp_path / f"f{ext}", tmp_path / "f.pdf"
    src.write_bytes(b"")
    office._com(src, out)
    names = _names(calls)
    assert progids == [progid]
    assert export in names and "Quit" in names and names[-1] == "CoUninitialize"
    assert names.index("Close") < names.index("Quit")
    assert any(c[:2] == ("set", "DisplayAlerts") for c in calls)  # no invisible modal prompt can hang the worker


def test_com_unknown_extension(fake_com, tmp_path: Path):
    calls, _ = fake_com
    with pytest.raises(ConversionError, match="no COM handler"):
        office._com(tmp_path / "f.odd", tmp_path / "f.pdf")
    assert "CoUninitialize" in _names(calls)


def test_com_available_respects_platform_and_env(monkeypatch):
    monkeypatch.setattr(office.sys, "platform", "win32")
    monkeypatch.delenv("PDF_HELPER_NO_COM", raising=False)
    assert office._com_available()
    monkeypatch.setenv("PDF_HELPER_NO_COM", "1")
    assert not office._com_available()
    monkeypatch.setattr(office.sys, "platform", "linux")
    monkeypatch.delenv("PDF_HELPER_NO_COM")
    assert not office._com_available()


def test_office_to_pdf_falls_back_after_com_failure(monkeypatch, tmp_path: Path, log):
    def broken_com(src, out):
        raise RuntimeError("no Word here")

    def fake_lo(src, out):
        out.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(office, "_com_available", lambda: True)
    monkeypatch.setattr(office, "_com", broken_com)
    monkeypatch.setattr(office, "_libreoffice", fake_lo)
    out = tmp_path / "f.pdf"
    office_to_pdf(tmp_path / "f.docx", out, log=log)
    assert out.exists() and "Microsoft Office failed" in log.lines[0]


def test_office_to_pdf_raises_when_nothing_works(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(office, "_com_available", lambda: False)
    monkeypatch.setattr(office, "find_libreoffice", lambda: None)
    with pytest.raises(ConversionError, match=r"install Microsoft Office or LibreOffice.*soffice not found"):
        office_to_pdf(tmp_path / "f.docx", tmp_path / "f.pdf", log=lambda _m: None)


def test_office_to_pdf_reports_silent_converter(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(office, "_com_available", lambda: False)
    monkeypatch.setattr(office, "_libreoffice", lambda src, out: None)  # returns without writing
    with pytest.raises(ConversionError, match="produced no output"):
        office_to_pdf(tmp_path / "f.docx", tmp_path / "f.pdf", log=lambda _m: None)


class _Proc:
    """A Popen stand-in: ``outcome`` is (returncode, stderr) or an exception to raise from communicate()."""

    started: list[list[str]] = []
    killed: list[int] = []

    def __init__(self, cmd, **kw):
        self.started.append(cmd)
        self.pid, self.returncode = 4242, None

    def communicate(self, timeout=None):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        self.returncode, stderr = self.outcome
        return b"", stderr

    def kill(self):
        self.killed.append(self.pid)

    def wait(self):
        pass


@pytest.fixture
def fake_soffice(monkeypatch):
    monkeypatch.setattr(office, "find_libreoffice", lambda: "soffice")
    monkeypatch.setattr(subprocess, "Popen", _Proc)
    _Proc.started, _Proc.killed = [], []

    def set_outcome(outcome):
        _Proc.outcome = outcome

    return set_outcome


def test_libreoffice_no_output(fake_soffice, tmp_path: Path):
    fake_soffice((0, b"Error: source file could not be loaded"))  # LibreOffice exits 0 on a load failure
    with pytest.raises(ConversionError, match="produced no output: Error: source file could not be loaded"):
        office._libreoffice(tmp_path / "f.docx", tmp_path / "f.pdf")


def test_find_libreoffice_windows_candidates(monkeypatch):
    monkeypatch.setattr(office.shutil, "which", lambda _n: None)
    monkeypatch.setattr(office, "_LIBREOFFICE_CANDIDATES", ("/nope/soffice.exe",))
    assert find_libreoffice() is None
    monkeypatch.setattr(office, "_LIBREOFFICE_CANDIDATES", (sys.executable,))
    assert find_libreoffice() == sys.executable


def test_libreoffice_surfaces_stderr_and_timeout(fake_soffice, tmp_path: Path):
    fake_soffice((1, b"Error: source file could not be loaded"))
    with pytest.raises(ConversionError, match="soffice failed: Error: source file could not be loaded"):
        office._libreoffice(tmp_path / "f.docx", tmp_path / "f.pdf")
    assert any(a.startswith("-env:UserInstallation=file:") for a in _Proc.started[0])

    fake_soffice((1, b""))
    with pytest.raises(ConversionError, match="exit status 1"):
        office._libreoffice(tmp_path / "f.docx", tmp_path / "f.pdf")

    fake_soffice(subprocess.TimeoutExpired(["soffice"], 180))
    with pytest.raises(ConversionError, match="timed out after 180 s"):
        office._libreoffice(tmp_path / "f.docx", tmp_path / "f.pdf")
    assert _Proc.killed == [4242]  # the process tree is killed, not left locking the profile


def test_kill_tree_uses_taskkill_on_windows(monkeypatch):
    ran: list[list[str]] = []
    monkeypatch.setattr(office.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: ran.append(cmd))
    proc = _Proc(["soffice"])
    office._kill_tree(proc)
    assert ran == [["taskkill", "/T", "/F", "/PID", "4242"]] and proc.killed[-1] == 4242


def test_com_quit_failure_is_logged_not_raised(fake_com, tmp_path: Path, caplog):
    calls, _ = fake_com

    class Stuck(_Fake):
        def __getattr__(self, name):
            if name == "Quit":
                raise RuntimeError("RPC server unavailable")
            return super().__getattr__(name)

    monkeypatch_client = sys.modules["win32com.client"]
    monkeypatch_client.DispatchEx = lambda progid: Stuck(calls)
    src = tmp_path / "f.docx"
    src.write_bytes(b"")
    office._com(src, tmp_path / "f.pdf")
    assert "did not quit" in caplog.text and _names(calls)[-1] == "CoUninitialize"
