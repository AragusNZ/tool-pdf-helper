# PDF Helper

Small Windows desktop tool for everyday PDF jobs. Drop files into the queue, press a button.

The buttons sit on five tabs.

### Convert

- **Create PDF(s)** – converts each queued file to a PDF saved next to it. When the queue holds images you pick the
  page they go on: **Auto (A4)** for A4 turned to match the picture, **Image size** for a page the size of the image
  itself, or A4, A3, A5, Letter, Legal, HD 1920x1080 or 4K 3840x2160 followed by portrait, landscape or match the
  image. The picture is scaled to fit and keeps its aspect ratio, and a multi-page TIFF gets one page per frame.
- **Merge to one PDF** – combines all queued files, in queue order, into a single PDF. Non-PDF files are converted
  first, images with the same page-size choice as Create PDF(s).
- **PDF to images** – one PNG per page at chosen DPI.
- **PDF to Word** – `.docx` via pdf2docx. Layout approximate. This dependency pulls in numpy + OpenCV and adds roughly 100 MB to the exe.
- **Extract content** – for each PDF, embedded images go to `<name>-content/images/`, plain text to `<name>-content/<name>.rtf`.
- **Tables to CSV** – every table found in each PDF, one `p<page>-<n>.csv` per table in `<name>-tables/`. Written as
  UTF-8 with a byte-order mark, which is what Excel needs to read accented text correctly.

### Pages

- **Extract pages** – queue one PDF, enter a page spec such as `1-3,5,8-`, save the result. Spec order is kept, so
  `3,1,2` reorders the pages as well as picking them.
- **Delete pages** – the other way round: name the pages to drop and keep the rest, as `<name>-trimmed.pdf`. Deleting
  every page is refused.
- **Split** – every N pages to its own file (`<name>-partNN.pdf`).
- **Split by bookmarks** – one file per top-level bookmark, named after it, into `<name>-chapters/`. A PDF without
  bookmarks is reported as an error and the rest of the queue carries on.
- **Rotate** – 90/180/270 on all pages or a page spec, single PDF.

### Stamp

- **Watermark** – diagonal grey text on every page, writes `<name>-stamped.pdf`.
- **Add text** – click the spot on a page preview, then pick the wording, font, size and colour. Applies to a page spec or every page of every queued PDF. Writes `<name>-text.pdf`.
- **Add image** – same click-to-place preview, with the width set in millimetres and the aspect ratio kept. Writes `<name>-image.pdf`.
- **Page numbers** – `1`, `1 of 10`, `Page 1` or `Page 1 of 10`, at any of six spots on the page. Numbering always
  starts at 1 on the first page. Writes `<name>-numbered.pdf`.

### Text

- **Replace text** – find and replace a string on every page, case-insensitive by default. Writes `<name>-replaced.pdf`. Replacements are drawn in Helvetica at the original size and colour; longer text is shrunk to fit.
- **Redact** – drag boxes on the page preview, and/or name a phrase to remove everywhere. Both are taken out of the
  file rather than covered over: the text is deleted from the page content and image pixels under a box go with it.
  Boxes are dragged on the first queued PDF and applied to every queued PDF, as Add text and Add image do. Writes
  `<name>-redacted.pdf`.
- **Find text** – lists which pages of which queued PDFs hold a phrase, in the log pane. Writes nothing, and matches
  inside words the same way Replace text does.

### Output

- **Compress** – downsample images (three presets), subset fonts, garbage-collect. Writes `<name>-small.pdf`.
- **Grayscale** – every colour to its grey equivalent, for cheaper printing. Writes `<name>-grey.pdf`.
- **N-up** – 2, 4 or 9 pages on each A4 sheet, the sheet turned to suit. Writes `<name>-4up.pdf`.
- **Resize pages** – scale every page onto A4, A3, A5, Letter, Legal, HD or 4K, portrait, landscape or turned to match
  the source. Writes `<name>-a4.pdf`.

Fonts for **Add text**: the 12 PDF base-14 text fonts (Helvetica, Times, Courier in four styles each) plus the `pymupdf-fonts` families (FiraGO, Fira Mono, Noto Sans, Ubuntu, Cascadia Mono, Space Mono). They are embedded in the PDF, so the output renders the same anywhere.

The queue takes **Delete** to drop the selected rows, and **Add files...** opens where the last batch came from.
The log file is capped at 1 MB with one previous copy kept.

**View > Theme** switches between System, Light and Dark; the choice is remembered. On System the app follows the
Windows light/dark setting and repaints when it changes. On Windows the native Windows 11 widget style draws the
controls; elsewhere it falls back to Fusion with the same colours.

Outputs never overwrite anything. The source file is refused as a target, and an output whose name is already taken
gets ` (2)`, ` (3)` and so on appended, so a second run never replaces the first one's files.
A failure on one file is logged and the rest of the queue still runs. Full tracebacks go to `PdfHelper.log` in the
system temp folder (`%TEMP%` on Windows); the log pane shows the path after any error.

Supported inputs: PDF; images (png, jpg, gif, bmp, tiff, webp); txt, epub, xps, svg, cbz; Office documents (doc/docx/rtf/odt, xls/xlsx/ods/csv, ppt/pptx/odp).

Office documents are converted with Microsoft Office if it is installed, otherwise LibreOffice. One of the two must be present for Office inputs.

## Limitations

- Watermark, Add text, Page numbers and Replace text draw with the PDF base fonts, which cover Latin scripts only. Text in Chinese,
  Japanese, Korean, Greek, Cyrillic or Arabic silently comes out blank.
- Replace text, Redact and Find text match inside words, so `cat` also hits `catalog`. A replacement wider than the
  text it replaces is drawn smaller so it still fits the original box.
- N-up and Resize pages copy page content only: annotations, form fields and links do not come across.
- Tables to CSV finds tables the way PyMuPDF does, from ruled lines and alignment. A table drawn with neither comes
  out as no table at all.

## Run from source

Linux / WSL (needs WSLg for the window):

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pdf_helper
pytest            # add --cov for a coverage report
```

Windows: same, but `py -3 -m venv .venv` and `.venv\Scripts\activate`.

## Build the exe

Always built with Windows Python, PyInstaller cannot cross-compile.

- From WSL: `./build.sh` (calls the Windows `py` launcher; venv and build dir go to `%LOCALAPPDATA%\pdf-helper`).
- From Windows: double-click `build.cmd` or run `build.ps1`.

Output: `dist\PdfHelper\PdfHelper.exe` plus `dist\PdfHelper-<version>.zip` and its `.sha256`. Copy `dist\` across.

The exe and window icon come from `pdf_helper/assets/icon.ico`. After editing `icon.svg` or `icon-16.svg`, regenerate
it with `python tools/make_icon.py` and commit the result.

Set `PDF_HELPER_NO_COM=1` to force the LibreOffice path when testing.

## Contributing

`AGENTS.md` has the module layout, the `Feature` contract a new button implements, and the
conventions that bite. `CHANGELOG.md` records every visible change under `## [Unreleased]`.
