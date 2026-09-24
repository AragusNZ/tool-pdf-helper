# pdf-helper

**Project type:** python-tool

<!-- The marker line above is parsed by the wiring tool. Keep the exact format.
     Shipping status is NOT declared here — it lives in the SHIPPING_STATUS file,
     which is the only source of truth. A missing file reads as Shipped. -->

Conventions load automatically from `~/dev/ai-agents`:

- **Claude**: channel rules via `.claude/rules/`, skills/agents via the `python-tool@aragusnz` plugin.
- **Cursor**: rules, skills, agents and the guard via `.cursor/`.

Both are generated from one source; edit `~/dev/ai-agents`, never the delivered files.

## What this is

A Windows desktop tool for everyday PDF jobs: files go into a queue, a button acts on all of them.
PySide6 for the window, PyMuPDF for everything that touches a PDF. Distributed as a PyInstaller onefile
exe; `README.md` is the user-facing half of this file.

## Layout

```
pdf_helper/
  app.py          the window, the button grid, logging setup — wires the rest together
  core/           pure PDF/file utilities, no Qt import anywhere
  features/       one file per button, plus base.py holding the Feature contract
  ui/             Qt widgets: file queue, dialogs, page-preview placement, theme, worker thread
  assets/         icon.ico and the SVGs it is generated from
tools/make_icon.py  regenerates assets/icon.ico from the SVGs
tests/            pytest, one file per core module or feature group
```

`VERSION` at the root is the only version source. `pdf_helper/__init__.py` reads it and `build.ps1`
bundles it into the exe, so the title bar and About box report the built version. Never hardcode it,
and never bump it — a bump is the operator's `dt patch`.

## Adding a feature

1. Create `pdf_helper/features/<name>.py` exposing
   `FEATURE = Feature(label=..., prepare=..., run=...)`. `prepare` runs on the UI thread and may
   open dialogs; `run` runs on a worker thread and **must not touch Qt**. `min_files`, `max_files`
   and `exts` gate when the button is enabled.
2. Append it to `FEATURES` in `pdf_helper/features/__init__.py` — that list is the button order.
3. Reusable PDF logic goes in `pdf_helper/core/`, with a test under `tests/`.

`each_file` in `features/base.py` is the batch helper: a failure on one file is logged and the rest
of the queue still runs. Outputs never overwrite the source file.

## Conventions that bite

- **No Qt outside `ui/`, `app.py` and a feature's `prepare`.** Worker-thread code that imports
  PySide6 widgets is the bug this layout exists to prevent.
- **Tracebacks go to `PdfHelper.log`** in the system temp folder — the exe has no console. The log
  pane shows the path after any error.
- **Office inputs** need Microsoft Office or LibreOffice on the machine. `PDF_HELPER_NO_COM=1`
  forces the LibreOffice path when testing.
- **Tests run offscreen.** `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`; the `qapp` fixture
  is the single `QApplication`.
- **The icon is generated.** After editing `icon.svg` or `icon-16.svg`, run
  `python tools/make_icon.py` and commit `assets/icon.ico`.

## Verify

```
. .venv/bin/activate
pytest                     # the whole gate; --cov for a coverage report
```

The exe is built with Windows Python (PyInstaller cannot cross-compile): `./build.sh` from WSL, or
`build.cmd` / `build.ps1` from Windows.
