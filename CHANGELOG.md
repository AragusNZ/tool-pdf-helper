# Changelog

## [Unreleased]

### Changed

- The exe now carries a version resource, so Windows shows "PDF Helper", "AragusNZ" and the version in its
  properties and in the SmartScreen prompt instead of calling it an unknown publisher.
- Built with `--onedir` and `--noupx` instead of `--onefile`. The onefile bootloader unpacked a Python runtime
  into `%TEMP%` on every launch, which is what antivirus flagged; startup is also faster now.
- Distributed as `PdfHelper-<version>-setup.exe`, an Inno Setup installer that installs per-user into
  `%LOCALAPPDATA%\Programs\PDF Helper` with no admin prompt. The zip is still built alongside it.
- Checksums moved to `dist\SHA256SUMS.txt`, covering the installer as well as the zip, and written as ASCII so
  `sha256sum -c` can read them.
- A `v*` tag now builds and publishes a GitHub release from a Windows runner; the `check` workflow moved to
  pushes on `main` and pull requests.
- `README.md` gained a "Windows security warnings" section: what the SmartScreen prompt means, `Unblock-File`
  for a download Windows refuses to open, and how to verify against the checksums.

## [1.0.1] - 2026-09-24

All notable changes to this project are documented here, in
[Keep a Changelog](https://keepachangelog.com) format.

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
