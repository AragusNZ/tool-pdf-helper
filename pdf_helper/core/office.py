"""Office document -> PDF. Tries Microsoft Office via COM, then LibreOffice headless."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

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
        except Exception as exc:  # noqa: BLE001 - any failure means try the next converter
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
    ext = src.suffix.lower()
    src_s, out_s = str(src.resolve()), str(out.resolve())
    try:
        if ext in _WORD:
            app = win32com.client.DispatchEx("Word.Application")
            app.Visible = False
            doc = app.Documents.Open(src_s, ReadOnly=True)
            try:
                doc.ExportAsFixedFormat(out_s, 17)  # wdExportFormatPDF
            finally:
                doc.Close(False)
        elif ext in _EXCEL:
            app = win32com.client.DispatchEx("Excel.Application")
            app.Visible = False
            wb = app.Workbooks.Open(src_s, ReadOnly=True)
            try:
                wb.ExportAsFixedFormat(0, out_s)  # xlTypePDF
            finally:
                wb.Close(False)
        elif ext in _POWERPOINT:
            app = win32com.client.DispatchEx("PowerPoint.Application")
            pres = app.Presentations.Open(src_s, ReadOnly=True, WithWindow=False)
            try:
                pres.SaveAs(out_s, 32)  # ppSaveAsPDF
            finally:
                pres.Close()
        else:
            raise ConversionError(f"no COM handler for {ext}")
    finally:
        try:
            app.Quit()  # type: ignore[possibly-undefined]
        except Exception:  # noqa: BLE001
            pass
        pythoncom.CoUninitialize()


def find_libreoffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    return next((p for p in _LIBREOFFICE_CANDIDATES if Path(p).exists()), None)


def _libreoffice(src: Path, out: Path) -> None:
    exe = find_libreoffice()
    if not exe:
        raise ConversionError("soffice not found")
    with tempfile.TemporaryDirectory() as tmp:
        # Private profile dir: otherwise a running LibreOffice window takes the job and we get no output.
        profile = Path(tmp, "profile").as_uri()
        cmd = [exe, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=_TIMEOUT)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode(errors="replace").strip() or f"exit status {exc.returncode}"
            raise ConversionError(f"soffice failed: {detail}") from None
        except subprocess.TimeoutExpired:
            raise ConversionError(f"soffice timed out after {_TIMEOUT} s") from None
        produced = Path(tmp) / f"{src.stem}.pdf"
        if not produced.exists():
            raise ConversionError("soffice produced no output")
        shutil.move(str(produced), str(out))
