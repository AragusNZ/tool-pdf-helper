"""Office document -> PDF. Tries Microsoft Office via COM, then LibreOffice headless."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# (COM ProgID, export callable) per extension
_WORD = {".doc", ".docx", ".rtf", ".odt", ".dot", ".dotx"}
_EXCEL = {".xls", ".xlsx", ".xlsm", ".ods", ".csv"}
_POWERPOINT = {".ppt", ".pptx", ".odp"}
OFFICE_EXTS = frozenset(_WORD | _EXCEL | _POWERPOINT)

_TIMEOUT = 180  # seconds per document

_LIBREOFFICE_CANDIDATES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


class ConversionError(RuntimeError):
    pass


def office_to_pdf(src: Path, out: Path, log=print) -> None:
    """Convert ``src`` to ``out``. Raises ConversionError if no converter works."""
    errors: list[str] = []
    converters = [("LibreOffice", _libreoffice)]
    if _com_available():
        converters.insert(0, ("Microsoft Office", _com))
    for name, fn in converters:
        try:
            fn(src, out)
            if out.exists():
                return
            errors.append(f"{name}: produced no output")
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            log(f"  {name} failed, trying next: {exc}")
    raise ConversionError(
        f"cannot convert {src.suffix}; install Microsoft Office or LibreOffice. " + "; ".join(errors)
    )


def _com_available() -> bool:
    return sys.platform == "win32" and not os.environ.get("PDF_HELPER_NO_COM")


def _com(src: Path, out: Path) -> None:
    import pythoncom  # type: ignore[import-not-found]
    import win32com.client  # type: ignore[import-not-found]

    pythoncom.CoInitialize()
    try:
        _com_export(win32com.client, src.suffix.lower(), str(src.resolve()), str(out.resolve()))
    finally:
        pythoncom.CoUninitialize()  # every COM proxy is out of scope by now; releasing one after this can crash


def _com_export(client, ext: str, src_s: str, out_s: str) -> None:
    """Open, export, close. DisplayAlerts off: a repair, links or password prompt from an invisible
    application would otherwise block the worker thread forever; off, it raises instead."""
    app = None
    try:
        if ext in _WORD:
            app = client.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0  # wdAlertsNone
            doc = app.Documents.Open(src_s, ReadOnly=True)
            try:
                doc.ExportAsFixedFormat(out_s, 17)  # wdExportFormatPDF
            finally:
                doc.Close(False)
        elif ext in _EXCEL:
            app = client.DispatchEx("Excel.Application")
            app.Visible = False
            app.DisplayAlerts = False
            wb = app.Workbooks.Open(src_s, ReadOnly=True)
            try:
                wb.ExportAsFixedFormat(0, out_s)  # xlTypePDF
            finally:
                wb.Close(False)
        elif ext in _POWERPOINT:
            app = client.DispatchEx("PowerPoint.Application")
            app.DisplayAlerts = 1  # ppAlertsNone
            pres = app.Presentations.Open(src_s, ReadOnly=True, WithWindow=False)
            try:
                pres.SaveAs(out_s, 32)  # ppSaveAsPDF
            finally:
                pres.Close()
        else:
            raise ConversionError(f"no COM handler for {ext}")
    finally:
        if app is not None:
            try:
                app.Quit()
            except Exception:
                log.warning("%s application did not quit; it may still be running hidden", ext, exc_info=True)


def find_libreoffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    return next((p for p in _LIBREOFFICE_CANDIDATES if Path(p).exists()), None)


def _libreoffice(src: Path, out: Path) -> None:
    exe = find_libreoffice()
    if not exe:
        raise ConversionError("soffice not found")
    # ignore_cleanup_errors: after a timeout the killed process may still hold the profile for a moment.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        # Private profile dir: otherwise a running LibreOffice window takes the job and we get no output.
        profile = Path(tmp, "profile").as_uri()
        cmd = [exe, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)]
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # type: ignore[attr-defined]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
        try:
            _, stderr = proc.communicate(timeout=_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            raise ConversionError(f"soffice timed out after {_TIMEOUT} s") from None
        detail = stderr.decode(errors="replace").strip()
        if proc.returncode:
            raise ConversionError(f"soffice failed: {detail or f'exit status {proc.returncode}'}")
        produced = Path(tmp) / f"{src.stem}.pdf"
        if not produced.exists():
            raise ConversionError("soffice produced no output" + (f": {detail}" if detail else ""))
        shutil.move(str(produced), str(out))


def _kill_tree(proc: subprocess.Popen) -> None:
    """On Windows soffice.exe is a launcher: killing it alone leaves soffice.bin running and the profile locked."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
    proc.kill()
    proc.wait()
