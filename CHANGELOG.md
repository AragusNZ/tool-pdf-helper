# Changelog

All notable changes to this project are documented here, in
[Keep a Changelog](https://keepachangelog.com) format.

## [Unreleased]

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
