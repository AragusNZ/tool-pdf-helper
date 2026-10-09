# PDF Helper

Small Windows desktop tool for everyday PDF jobs. Drop files into the queue, pick an action, press **Run**.

No account, no upload: every file is processed on your own machine. The only thing it asks the internet is
whether a newer version is out, and nothing about your files goes with it.

## Install

Download the latest **`PdfHelper-<version>-setup.exe`** from
[Releases](https://github.com/AragusNZ/tool-pdf-helper/releases) and run it.

- It installs per-user into `%LOCALAPPDATA%\Programs\PDF Helper` and never asks for admin rights.
- Windows 10 or 11, 64-bit. Nothing else to install, unless you feed it Office documents — see below.
- Windows will warn about the publisher. That is expected, and [what to do](#windows-security-warnings) is below.
- `PdfHelper-<version>.zip` is the same program as a plain folder, for a machine where installers are blocked.
  Unzip it anywhere and run `PdfHelper.exe`.
- To update: on start it checks GitHub for a newer release and offers to open the download page.
  **Help > Check for Updates** asks any time; untick **Help > Check on Startup** to stop the automatic check.
  Run the new `setup.exe` over the top — it upgrades in place and keeps your settings.
- Right-click files in Explorer and choose **Send to > PDF Helper** to open them straight into the queue.
- To remove it: **Settings > Apps > Installed apps > PDF Helper > Uninstall**.

Verify a download against `SHA256SUMS.txt` from the same release:

```
Get-FileHash .\PdfHelper-<version>-setup.exe -Algorithm SHA256
```

## What it does

Add files with **Add files...** or by dropping them on the file list, then pick an action and press **Run** under the
tabs. Every action works on the whole queue. The actions sit on five tabs.

**Run** asks for the action's options, then where to save. With one file queued you name the output file. With
several you pick a folder and the text added to each file's name — `-small` turns `invoice.pdf` into
`invoice-small.pdf`. The names below are those defaults.

While a job runs, a dialog counts files done and **Cancel** stops it after the current file; nothing else in the
window responds until it is over. When it finishes, the dialog says whether it worked, in green, or failed, in red,
with **OK** and, when files were written, **Open output folder**. **Details** in the dialog lists what happened to
each file; it opens by itself when one fails. The line beside **Run** repeats the result after the dialog closes.
Untick **View > Block the window while a job runs** to keep the queue editable during a job; the status bar
counts files done either way.

### Convert

- **Create PDF(s)** – converts each queued file to a PDF saved next to it. When the queue holds images you pick the
  page they go on: **Auto (A4)** for A4 turned to match the picture, **Image size** for a page the size of the image
  itself, or A4, A3, A5, Letter, Legal, HD 1920x1080 or 4K 3840x2160 followed by portrait, landscape or match the
  image. The picture is scaled to fit and keeps its aspect ratio, and a multi-page TIFF gets one page per frame.
- **Merge to one PDF** – combines all queued files, in queue order, into a single PDF. Non-PDF files are converted
  first, images with the same page-size choice as Create PDF(s).
- **PDF to images** – one PNG per page at chosen DPI.
- **PDF to Word** – `.docx` via pdf2docx. Layout approximate.
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

### Edit

- **Edit** – stack several changes on a page preview, each placed over the ones before, then save once as
  `<name>-edited.pdf`. The preview shows the first queued PDF; every edit applies to every queued one.
  - **Add text** – click the spot on the page, then pick the wording, font, size and colour, for a page spec or
    every page. The preview shows the text as it will print; drag it to move it.
  - **Add image** – same click-to-place and drag-to-move, with the width set in millimetres and the aspect ratio
    kept.
  - **Page numbers** – `1`, `1 of 10`, `Page 1` or `Page 1 of 10`, at any of six spots on the page. Numbering always
    starts at 1 on the first page.
  - **Watermark** – diagonal grey text on every page.
  - **Replace text** – find and replace a string on every page, case-insensitive by default. Replacements are drawn
    in Helvetica (Noto Sans when the text needs more than Latin-1) at the original size and colour; longer text is
    shrunk to fit.

  The list shows the edits in the order they apply; **Move up** / **Move down** reorder them, **Remove** (or the
  Delete key) drops one, and selecting a text or image edit outlines it on the preview. After a Replace text edit
  the status line says how many hits it had on the previewed file, so a Find text that matched nothing shows as
  `0 replacement(s)`. **Save PDF...** asks where to write before the editor closes; cancelling that keeps the edits.

  **Save edits...** writes the pending list to a `.pdfedits.json` file; **Load edits...** brings it back, onto the
  same PDF another day or onto different ones.

### Text

- **Redact** – drag boxes on the page preview, and/or name a phrase to remove everywhere. Both are taken out of the
  file rather than covered over: the text is deleted from the page content and image pixels under a box go with it.
  Boxes are dragged on the first queued PDF and applied to every queued PDF, as Edit does. Writes
  `<name>-redacted.pdf`.
- **Find text** – lists which pages of which queued PDFs hold a phrase, under **Details** in the run dialog. Writes nothing, and matches
  inside words the same way Replace text does.
- **Footnote comments** – turns reviewer comments into footnotes. Every annotation with a comment (highlight,
  underline, strike-out, sticky note, box, circle, line, ink) gets a small red number, and the comments are listed
  on notes pages, numbered through the whole file. Numbers link to their note and back, the notes pages are
  bookmarked, and replies sit under the comment they answer. One dialog picks: quote the highlighted text, list
  highlights that have no comment, show the reviewer's name, keep or flatten the highlights, notes after each page
  / at the end / on their own, the wording of the notes heading before the page number, number in the right margin / left margin / after the phrase / on the highlight's top-left corner, a line and bubble joining a margin number to its highlight, its size and colour, an optional disc in its own colour (presets or
  a colour picker for both), and an extra `<name>-notes.md`. Writes `<name>-notes.pdf`.

### Output

- **Compress** – downsample images (three presets), subset fonts, garbage-collect. Writes `<name>-small.pdf`.
- **Grayscale** – every colour to its grey equivalent, for cheaper printing. Writes `<name>-grey.pdf`.
- **N-up** – 2, 4 or 9 pages on each A4 sheet, the sheet turned to suit. Writes `<name>-4up.pdf`.
- **Resize pages** – scale every page onto A4, A3, A5, Letter, Legal, HD or 4K, portrait, landscape or turned to match
  the source. Writes `<name>-a4.pdf`.
- **Password protect** – a copy that asks for a password to open (AES-256). You type it twice. Writes
  `<name>-protected.pdf`.
- **Unlock** – a copy without the password. You need to know the password. Writes `<name>-unlocked.pdf`.
- **Edit info** – title, author, subject and keywords. With one file the boxes show what it has now; a blank box is
  left as it is. Writes `<name>-info.pdf`.

## Good to know

**Inputs.** PDF; images (png, jpg, gif, bmp, tiff, webp, pnm/pgm/ppm); txt, epub, mobi, fb2, xps, svg, cbz; Office documents
(doc/docx/rtf/odt, xls/xlsx/ods/csv, ppt/pptx/odp). Office documents are converted with Microsoft Office if it is
installed, otherwise LibreOffice — one of the two must be present for those inputs, and nothing else needs it.

**Nothing is overwritten without asking.** The source file is refused as a target. An automatic name that is already taken
gets ` (2)`, ` (3)` and so on appended, so a second run never replaces the first one's files. A name you pick in a
Save dialog is replaced only after Windows asks you to confirm.

**One bad file does not stop the batch.** The failure is logged and the rest of the queue still runs. Full
tracebacks go to `PdfHelper.log` in the system temp folder (`%TEMP%`); **Details** shows the path after any error.
The log is capped at 1 MB with one previous copy kept.

**Fonts for Edit > Add text.** The 12 PDF base-14 text fonts (Helvetica, Times, Courier in four styles each) plus the
`pymupdf-fonts` families (FiraGO, Fira Mono, Noto Sans, Ubuntu, Cascadia Mono, Space Mono). The `pymupdf-fonts`
families are embedded in the PDF; the base-14 fonts are not, as every PDF viewer carries them.

**Queue.** **Delete** drops the selected rows; **Add files...** opens where the last batch came from.

**View > Theme** switches between System, Light and Dark; the choice is remembered. On System the app follows the
Windows light/dark setting and repaints when it changes. On Windows the native Windows 11 widget style draws the
controls; elsewhere it falls back to Fusion with the same colours.

## Limitations

- Watermark, Page numbers and Replace text draw with Helvetica, and switch to Noto Sans when the text has characters
  outside Latin-1 (macrons, Greek, Cyrillic). Chinese, Japanese, Korean and Arabic are not covered; pick a font that
  has them in Edit > Add text.
- Replace text on a phrase that wraps from one line to the next draws the replacement on each line.
- Replace text, Redact and Find text match inside words, so `cat` also hits `catalog`. A replacement wider than the
  text it replaces is drawn smaller so it still fits the original box.
- N-up and Resize pages copy page content only: annotations, form fields and links do not come across.
- Tables to CSV finds tables the way PyMuPDF does, from ruled lines and alignment. A table drawn with neither comes
  out as no table at all.
- PDF to Word approximates the layout. Treat the `.docx` as a starting point, not a faithful copy.

## Windows security warnings

The build is **not code-signed** — a certificate needs a hardware token or cloud HSM and an annual fee, and this
tool is not yet worth one. So Windows will not vouch for the publisher, and three things can happen:

- **"Windows protected your PC."** SmartScreen does not recognise the file yet. Click **More info**, then
  **Run anyway**. This fades as more people download the same release.
- **"Windows cannot access the specified device, path or file."** The download carries a Mark-of-the-Web, or
  Defender has quarantined it. Clear the first with PowerShell in the download folder:

  ```
  Unblock-File .\PdfHelper-<version>-setup.exe
  ```

  If that does not help, check Windows Security > Protection history for a block on `PdfHelper.exe`.
- **An antivirus flags the exe.** A false positive: PyInstaller bundles a Python runtime, and that shape is what
  gets flagged. Verify the download against `SHA256SUMS.txt` before allowing it, as shown under [Install](#install).

Only download from the [Releases page](https://github.com/AragusNZ/tool-pdf-helper/releases). A copy passed around
by hand is both unverifiable and slower to earn SmartScreen's trust.

## Something went wrong

1. Open **Details** in the run dialog, or **Help > Show Log** afterwards — the error names the file it failed on.
2. Open `PdfHelper.log` in `%TEMP%` for the full traceback (**Open log file** in the log window). Details prints
   its path after any error.
3. Report it at [Issues](https://github.com/AragusNZ/tool-pdf-helper/issues) with that traceback, the button you
   pressed and the version from **Help > About**.

## Developing

Python 3.12, PySide6 and PyMuPDF. Source, issues and the full change history live at
[AragusNZ/tool-pdf-helper](https://github.com/AragusNZ/tool-pdf-helper). To run it from source, add a button,
run the tests or build the installer, see
[CONTRIBUTING.md](https://github.com/AragusNZ/tool-pdf-helper/blob/main/CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](https://github.com/AragusNZ/tool-pdf-helper/blob/main/LICENSE), which also ships in the
install folder. PyMuPDF is AGPL-licensed; a build that links it and is redistributed carries that obligation.
