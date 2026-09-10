# PDF Helper

Small Windows desktop tool for everyday PDF jobs. Drop files into the queue, press a button.

Features:

- **Create PDF(s)** – converts each queued file to a PDF saved next to it.
- **Merge to one PDF** – combines all queued files, in queue order, into a single PDF. Non-PDF files are converted first.
- **Extract pages** – queue one PDF, enter a page spec such as `1-3,5,8-`, save the result.
- **Extract content** – for each PDF, embedded images go to `<name>-content/images/`, plain text to `<name>-content/<name>.rtf`.
- **Split** – every N pages to its own file (`<name>-partNN.pdf`).
- **Rotate** – 90/180/270 on all pages or a page spec, single PDF.
- **Compress** – downsample images (three presets), subset fonts, garbage-collect. Writes `<name>-small.pdf`.
- **PDF to images** – one PNG per page at chosen DPI.
- **Watermark** – diagonal grey text on every page, writes `<name>-stamped.pdf`.
- **Replace text** – find and replace a string on every page, case-insensitive by default. Writes `<name>-replaced.pdf`. Replacements are drawn in Helvetica at the original size and colour; longer text is shrunk to fit.
- **PDF to Word** – `.docx` via pdf2docx. Layout approximate. This dependency pulls in numpy + OpenCV and adds roughly 100 MB to the exe.

Outputs never overwrite the source file. Create PDF(s) and PDF to Word skip a file whose target already exists.
A failure on one file is logged and the rest of the queue still runs. Full tracebacks go to `PdfHelper.log` in the
system temp folder (`%TEMP%` on Windows); the log pane shows the path after any error.

Supported inputs: PDF; images (png, jpg, gif, bmp, tiff, webp); txt, epub, xps, svg, cbz; Office documents (doc/docx/rtf/odt, xls/xlsx/ods/csv, ppt/pptx/odp).

Office documents are converted with Microsoft Office if it is installed, otherwise LibreOffice. One of the two must be present for Office inputs.

## Run from source

```
python -m venv .venv
.venv\Scripts\activate          # Linux/WSL: . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pdf_helper
pytest            # add --cov for a coverage report
```

## Build the exe (Windows)

Double-click `build.cmd` or run `build.ps1`. Output: `dist\PdfHelper\PdfHelper.exe` plus `dist\PdfHelper-<version>.zip` and its `.sha256`.

Set `PDF_HELPER_NO_COM=1` to force the LibreOffice path when testing.

## Adding a feature

1. Create `pdf_helper/features/<name>.py` exposing `FEATURE = Feature(label=..., prepare=..., run=...)`.
   `prepare` runs on the UI thread and may open dialogs; `run` runs on a worker thread and must not touch Qt.
2. Append it to `FEATURES` in `pdf_helper/features/__init__.py`.
3. Put reusable PDF logic in `pdf_helper/core/` with a test under `tests/`.

Layout: `core/` pure utilities (no Qt), `features/` one file per button, `ui/` Qt widgets, `app.py` wires them.
