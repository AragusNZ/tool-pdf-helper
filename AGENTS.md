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
PySide6 for the window, PyMuPDF for everything that touches a PDF. Distributed as a PyInstaller onedir
build wrapped in an Inno Setup installer, cut by the `release` workflow on a `v*` tag.

`README.md` is user-facing only and `build.ps1` copies it into the shipped build, so nothing about building
or contributing belongs in it. `CONTRIBUTING.md` is the human long form of this file: release steps, the
`Feature` example in full, and why each build flag is there.

## Layout

```
pdf_helper/
  app.py          the window, the Actions tabs, logging setup — wires the rest together
  core/           pure PDF/file utilities, no Qt import anywhere
  features/       one file per button, plus base.py holding the Feature contract
  ui/             Qt widgets: file queue, dialogs, page preview, placement and redaction, theme, worker
  assets/         icon.ico and the SVGs it is generated from
tools/make_icon.py  regenerates assets/icon.ico from the SVGs
tests/            pytest, one file per core module or feature group
packaging/pdf-helper.iss  the Inno Setup installer, compiled by build.ps1
```

The exe is unsigned, so everything about the build that Windows reads as trust or as an antivirus
heuristic is deliberate: `--onedir` (not onefile — no self-extract into `%TEMP%`), `--noupx`, the
`--version-file` resource `build.ps1` generates from `VERSION`, and `PrivilegesRequired=lowest` in the
`.iss` so the installer never triggers UAC. Do not undo one of those to shorten the build.

`VERSION` at the root is the only version source. `pdf_helper/__init__.py` reads it and `build.ps1`
bundles it into the exe, so the title bar and About box report the built version. Never hardcode it,
and never bump it — a bump is the operator's `dt patch`.

## Adding a feature

1. Create `pdf_helper/features/<name>.py` exposing
   `FEATURE = Feature(label=..., prepare=..., run=...)`. `prepare` runs on the UI thread and may
   open dialogs; `run` runs on a worker thread and **must not touch Qt**. `min_files`, `max_files`
   and `exts` gate when the button is enabled; `group` is the Actions tab it lands on.
2. Append it to `FEATURES` in `pdf_helper/features/__init__.py` — that list is the button order, and
   the first appearance of each `group` is the tab order. Keep a group's features together.
3. Reusable PDF logic goes in `pdf_helper/core/`, with a test under `tests/`.

`ask_page_spec` in `ui/dialogs.py` is the "1-3,5" prompt: it re-asks until the spec parses, and
returns `[]` for a blank one when `allow_blank` is set.

`each_file` in `features/base.py` is the batch helper: a failure on one file is logged and the rest
of the queue still runs. It also drives the progress bar and Cancel (between files). `fn` returns the
file or folder it wrote, which feeds **Open output folder**; a feature that skips `each_file`
appends to `ctx.outputs` itself. Outputs never overwrite anything: `core/pdf.py` refuses a source file as a target,
and every generated name goes through `fresh` in `core/paths.py`, which appends ` (2)` when it is taken.

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

CI fails under 95% coverage.

The exe is built with Windows Python (PyInstaller cannot cross-compile): `./build.sh` from WSL, or
`build.cmd` / `build.ps1` from Windows.
