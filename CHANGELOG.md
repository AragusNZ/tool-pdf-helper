# Changelog

All notable changes to this project are documented here, in
[Keep a Changelog](https://keepachangelog.com) format.

## [Unreleased]

## [1.3.1] - 2026-10-09

### Fixed

- Rotated pages: Redact boxes, Add text, Add image, Page numbers and Watermark now land where the preview showed
  them. They were placed in the page's unrotated space, so on a page turned 90° a box blacked out the wrong area and
  text ran sideways down the far edge.
- Match case in Redact, Replace text and Find text missed a phrase that wrapped from one line to the next, so a
  case-sensitive redaction could leave it in the file. Each line of the hit now counts.
- Watermark, Page numbers and Replace text switch to Noto Sans for text outside Latin-1, so "Māori" no longer comes
  out as "M·ori".
- Footnote comments "after each page" sized every notes page from the wrong page once earlier notes pages had been
  inserted; a landscape page now gets a landscape notes page.
- Split by bookmarks dropped the pages before the first bookmark; they now come out as `<name>-01 front matter.pdf`.
- Create PDF and Merge onto a fixed page size (A4, Letter...) downsampled every image to 72 dpi. A scan keeps its
  pixels, and a JPEG its stream.
- Merge honours Cancel between files and counts them on the progress bar.
- Open output folder no longer reopens the previous job's folder after a job that wrote nothing.
- Help > Check for Updates says so when a check is already running instead of doing nothing.
- Dropping a folder the app cannot read no longer crashes it; the folder is logged as skipped. The same file added
  by a relative and an absolute path is queued once.
- A stored theme the app does not know (an old or hand-edited setting) no longer stops it at startup.
- A Find or Watermark text of only spaces is treated as a cancel.
- Office conversion: Word, Excel and PowerPoint run with alerts off, so a repair, links or password prompt from the
  invisible application raises an error instead of hanging the job for ever; an application that will not quit is
  logged. A LibreOffice timeout now kills `soffice.bin` as well as its launcher and reports the timeout rather than a
  locked profile folder, and LibreOffice's own error is shown when it exits cleanly without writing a PDF.
- The page preview in Add text, Add image and Redact shrinks on short screens so the bottom of the page can be clicked.
- Compress says when the output is no smaller than the original.

### Changed

- `pytest --cov` fails locally under 95% coverage, the same gate as CI. The test suite keeps its settings in a
  temp folder instead of the real user settings.

### Internal

- `check` runs on every push to `main`, not only tags and pull requests. `release` refuses a tag that does not
  match `VERSION`, runs the coverage gate on Windows and fails if an asset is missing. The installer removes the
  previous `_internal` on upgrade and refuses 32-bit or pre-Windows 10 machines.

## [1.3.0] - 2026-10-09

### Added

- **Footnote comments** on the Text tab: every annotation that carries a comment (highlight, underline,
  strike-out, sticky note, box, circle, line, ink) gets a small red number, and the comments are listed on notes
  pages. Numbers run through the whole file; each number links to its note and back, and the notes pages are
  bookmarked. Replies are listed under the comment they answer. One dialog picks the options: quote the
  highlighted text or not, list highlights that have no comment, show the reviewer's name, keep the highlights
  as annotations or flatten them into the page, put the notes after each page / at the end / on their own,
  put the number in the right margin / left margin / after the phrase, pick its size and colour, give it a disc in a colour
  of your own (presets or a colour picker for both), and also write `<name>-notes.md`.
  Writes `<name>-notes.pdf`.

## [1.2.0] - 2026-09-25

### Added

- Update check: on start, PDF Helper asks GitHub for the latest release and, if it is newer, offers to open
  the download page. **Help > Check for Updates** runs it on demand; **Help > Check on Startup** turns the
  automatic check off. Nothing is downloaded or installed by the app itself.
- **Cancel** in the status bar stops a running batch after the current file, and the progress bar now counts
  files done ("3 of 10") instead of just spinning.
- **Open output folder**, under the log, opens the folder the last job wrote to.
- Files named on the command line are queued at start, and the installer adds **Send to > PDF Helper** to
  Explorer's right-click menu.
- The window reopens at the size and position it was closed at.
- **Password protect**, **Unlock** and **Edit info** (title, author, subject, keywords) on the Output tab. A
  password-protected input to any other button now says to use Unlock first.

## [1.1.0] - 2026-09-24

### Added

- `LICENSE` — MIT, `Copyright (c) AragusNZ`. `build.ps1` copies it into the build, so it ships in the
  installer and the zip alongside the README, and the installer now opens on a licence page.

### Changed

- The exe now carries a version resource, so Windows shows "PDF Helper", "AragusNZ" and the version in its
  properties and in the SmartScreen prompt instead of calling it an unknown publisher. The
  `LegalCopyright` field reads `Copyright (c) AragusNZ`, with no personal name and no year to go stale.
- Built with `--onedir` and `--noupx` instead of `--onefile`. The onefile bootloader unpacked a Python runtime
  into `%TEMP%` on every launch, which is what antivirus flagged; startup is also faster now.
- Distributed as `PdfHelper-<version>-setup.exe`, an Inno Setup installer that installs per-user into
  `%LOCALAPPDATA%\Programs\PDF Helper` with no admin prompt. The zip is still built alongside it.
- Checksums moved to `dist\SHA256SUMS.txt`, covering the installer as well as the zip, and written as ASCII so
  `sha256sum -c` can read them.
- A `v*` tag now builds and publishes a GitHub release from a Windows runner, so the download has a stable URL
  that SmartScreen can accumulate reputation against.
- `README.md` gained a "Windows security warnings" section: what the SmartScreen prompt means, `Unblock-File`
  for a download Windows refuses to open, and how to verify against the checksums.
- `README.md` is now user-facing only — install, what each button does, limitations, Windows security warnings
  and where the log is. It is the copy `build.ps1` ships inside the installer and the zip, so the build,
  release and contributor material that used to ride along with it moved to a new `CONTRIBUTING.md`.

## [1.0.1] - 2026-09-24

Release plumbing only; nothing changed in the app itself. The `check` workflow moved to `v*` tags and
pull requests.

## [1.0.0] - 2026-09-24

### Fixed

- Merging into a file that was also an input silently replaced that input. Writing a PDF over one of its own source
  files is now refused with a plain message, in Merge, Extract pages and Rotate.
- A page named twice in a page spec, as in `1,1`, was acted on twice: Rotate turned it 180 instead of 90, and Add
  text and Add image drew on top of themselves. Extract pages still honours repeats, which is what a spec like
  `3,1,1` is for.
- Replace text wrapped a longer replacement inside the old box (`elephant` came out as `eleph` / `ant`) despite the
  documentation promising it was shrunk to fit. It is now drawn on one line at a size that fits.
- The queue accepted a file that did not exist, which then failed on the worker thread once the job started.
- The page preview in Add text and Add image reported a placement point for a click past the edge of the page image.
- `pytest` collected nothing outside an installed checkout — every test module failed on
  `No module named 'pdf_helper'`, so the `check` workflow was red. `pythonpath = ["."]` in
  `pyproject.toml` puts the repo root on `sys.path`.

### Changed

- No output ever replaces an existing file. A name that is taken gets ` (2)`, ` (3)` and so on appended, which
  replaces the "skip a file whose target already exists" behaviour of Create PDF(s) and PDF to Word and covers every
  other action, including a second run into the same folder.

### Added

- Nine buttons, all on PyMuPDF features the tool already shipped the library for: **Delete pages**, **Split by
  bookmarks**, **Page numbers**, **N-up**, **Resize pages**, **Grayscale**, **Tables to CSV**, **Find text** and
  **Redact**. No new dependency.
- Redact takes boxes dragged over the page preview as well as a phrase, and removes both from the file rather than
  covering them: the text goes out of the page content and image pixels under a box go with it.
- The Actions area is now five tabs - Convert, Pages, Stamp, Text, Output - because 22 buttons in one grid was a wall.
  A feature declares its tab with the new `group` field on `Feature`.

- Create PDF(s) and Merge ask what page images go on: Auto (A4 turned to match the picture), Image size (a page the
  size of the image, as before), or A4, A3, A5, Letter, Legal, HD 1920x1080 or 4K 3840x2160 with a portrait,
  landscape or match-the-image orientation. A multi-page TIFF gets one page per frame.
- The file queue takes the Delete key, and Add files... opens where the last batch came from.
- `PdfHelper.log` is capped at 1 MB with one previous copy kept, rather than growing without limit.
- `tests/test_pipeline.py` — end-to-end runs of the real features through `MainWindow`: queue,
  button gating, dialogs, worker thread and the files on disk, including a batch where one PDF is
  unreadable and the rest must still run. Plus the `main()` entry point, the theme menu and the
  About box.
- CI runs `pytest --cov --cov-fail-under=95`, so a coverage regression fails the workflow.

## [0.2.0] - 2026-09-24

### Added

- **Add text** — click the spot on a page preview, then choose the wording, font, size and colour.
  Applies to a page spec or every page of every queued PDF, and writes `<name>-text.pdf`. Fonts are
  the 12 PDF base-14 faces plus the `pymupdf-fonts` families, embedded in the output.
- **Add image** — the same click-to-place preview, with the width set in millimetres and the aspect
  ratio kept. Writes `<name>-image.pdf`.
- **View > Theme** — System, Light or Dark, remembered between runs. On System the app follows the
  Windows setting and repaints when it changes; on Windows the native Windows 11 widget style draws
  the controls, elsewhere Fusion with the same colours.

### Changed

- The version is read from the root `VERSION` file at import rather than hardcoded in
  `pdf_helper/__init__.py`. The exe carries the file, so the title bar and About box report the
  built version.
- `build.sh` runs the Windows Python from WSL, and the README covers running from source on both
  platforms.

### Internal

- Wired to the `python-tool` channel of `~/dev/ai-agents`: channel rules and skills load from the
  plugin, `dt` runs the suite and the release, and a `check` workflow gates every push.

## [0.1.0] - 2026-09-10

### Added

- First cut: the file queue and the buttons around it — create PDFs, merge, extract pages, extract
  content, split, rotate, compress, PDF to images, watermark, replace text and PDF to Word.
  Outputs never overwrite the source, a failure on one file leaves the rest of the queue running,
  and tracebacks go to `PdfHelper.log` in the system temp folder.
- Office inputs through Microsoft Office when installed, LibreOffice otherwise
  (`PDF_HELPER_NO_COM=1` forces the LibreOffice path).
- Windows build: `build.ps1` / `build.cmd` produce `dist\PdfHelper\PdfHelper.exe` plus a versioned
  zip and its `.sha256`.
