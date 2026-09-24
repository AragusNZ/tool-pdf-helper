# Contributing

PDF Helper is a Windows desktop tool built on PySide6 (the window) and PyMuPDF (everything that touches a PDF).
It ships as a PyInstaller `--onedir` build wrapped in an Inno Setup installer.

[README.md](README.md) is the user-facing half of this document. [AGENTS.md](AGENTS.md) is the same ground
compressed for coding agents.

## Run from source

Python 3.12. Linux/WSL works for development — you need WSLg for the window — but the exe can only be built on
Windows.

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pdf_helper
```

On Windows: `py -3 -m venv .venv` and `.venv\Scripts\activate`, the rest is the same.

Office inputs need Microsoft Office or LibreOffice on the machine. `PDF_HELPER_NO_COM=1` forces the LibreOffice
path, which is how you test that branch on a machine that has Office.

## Tests

```
pytest            # the whole gate
pytest --cov      # coverage report
```

CI fails under 95% coverage (`.github/workflows/check.yml`), so a new module or feature lands with its test.
`tests/` holds one file per core module or feature group.

Qt runs offscreen: `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`, and the `qapp` fixture is the single
`QApplication` for the session. Never construct a second one.

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

`core/` is importable from a script or a test with no Qt in sight; that separation is the point of the split, not
a stylistic preference.

## Adding a button

A button is a `Feature`. The app knows nothing else about it — no registration ceremony, no base class.

1. Create `pdf_helper/features/<name>.py` exposing a module-level `FEATURE`:

   ```python
   """One line saying what the button does."""

   from pathlib import Path

   from pdf_helper.core.paths import fresh
   from pdf_helper.core.pdf import grayscale
   from pdf_helper.features.base import PDF_ONLY, Feature, FeatureContext, each_file
   from pdf_helper.ui.dialogs import choose_directory


   def prepare(ctx: FeatureContext) -> Path | None:
       return choose_directory(ctx.parent, ctx.files[0].parent)


   def run(ctx: FeatureContext, out_dir: Path) -> None:
       def one(src: Path) -> Path:
           out = fresh(out_dir / f"{src.stem}-grey.pdf")
           grayscale(src, out)
           ctx.log(f"{src.name}: grey -> {out}")
           return out  # feeds "Open output folder"

       each_file(ctx, one)


   FEATURE = Feature(
       label="Grayscale", prepare=prepare, run=run, exts=PDF_ONLY, group="Output",
       tooltip="Convert every colour to grey",
   )
   ```

2. Append it to `FEATURES` in `pdf_helper/features/__init__.py`. That list is the button order, and the first
   appearance of each `group` is the tab order — so keep a group's features together.
3. Reusable PDF logic goes in `pdf_helper/core/`, with a test under `tests/`.

### The contract

| Field | Meaning |
|---|---|
| `label` | button text |
| `prepare` | runs on the **UI thread**, may open dialogs. Returns the value passed to `run`, or `None` to cancel. Optional. |
| `run` | runs on a **worker thread**. Must not touch Qt. |
| `min_files`, `max_files` | queue size that enables the button |
| `exts` | allowed extensions; `None` means any supported input |
| `group` | the Actions tab it lands on |
| `tooltip` | hover text |

Helpers you should be using rather than reimplementing:

- **`each_file(ctx, fn)`** in `features/base.py` — the batch loop. A failure on one file is logged and the rest of
  the queue still runs; the count is raised at the end. It also reports progress and honours Cancel between
  files. `fn` returns the file or folder it wrote (or `None`); a feature that does not use `each_file` appends to
  `ctx.outputs` itself.
- **`fresh(path)`** in `core/paths.py` — appends ` (2)`, ` (3)` until the name is free. Every generated output name
  goes through it.
- **`ask_page_spec`** in `ui/dialogs.py` — the `1-3,5` prompt. Re-asks until the spec parses, and returns `[]` for
  a blank one when `allow_blank` is set.
- **`ctx.log(...)`** — one line per file, to the log pane.

## Conventions that bite

- **No Qt outside `ui/`, `app.py` and a feature's `prepare`.** Worker-thread code importing PySide6 widgets is the
  bug this layout exists to prevent.
- **Nothing overwrites anything.** `core/pdf.py` refuses a source file as a target, and every generated name goes
  through `fresh`.
- **Tracebacks go to `PdfHelper.log`** in the system temp folder — the exe has no console, so an exception that
  only reaches stderr is an exception nobody ever sees.
- **The icon is generated.** After editing `pdf_helper/assets/icon.svg` or `icon-16.svg`, run
  `python tools/make_icon.py` and commit `assets/icon.ico`.
- **Never hardcode or bump the version.** The root `VERSION` file is the only source; `pdf_helper/__init__.py`
  reads it and `build.ps1` bundles it, so the title bar, the About box and the exe properties all report the built
  version. A bump is the operator's `dt patch`.
- **Record visible changes** in `CHANGELOG.md` under `## [Unreleased]`, in
  [Keep a Changelog](https://keepachangelog.com) form. Behaviour a user could notice belongs there; a refactor does
  not.

## Build the exe

Always built with Windows Python — PyInstaller cannot cross-compile.

- From WSL: `./build.sh`. It calls the Windows `py` launcher; the venv and build directory go to
  `%LOCALAPPDATA%\pdf-helper`, because pip over `\\wsl.localhost` is unusably slow.
- From Windows: double-click `build.cmd`, or run `build.ps1`.

Inno Setup 6 builds the installer: `winget install JRSoftware.InnoSetup`. Without it the build still runs and just
skips that one step.

Output in `dist\`:

| File | What it is |
|---|---|
| `PdfHelper\PdfHelper.exe` + `_internal\` | the app itself, a `--onedir` build |
| `PdfHelper-<version>-setup.exe` | the installer — what you hand to anyone else |
| `PdfHelper-<version>.zip` | the same folder zipped, for a machine that cannot run an installer |
| `SHA256SUMS.txt` | checksums of both |

`build.ps1` copies `README.md` and `LICENSE` into `dist\PdfHelper\`, so both ship inside the installer and
the zip. Keep the README user-facing — a contributor-only section in there is a section every end user gets.

### Why the build looks the way it does

The exe is unsigned, so everything Windows reads as trust or as an antivirus heuristic is deliberate. Do not undo
one of these to shorten the build:

- **`--onedir`, not `--onefile`.** A onefile bootloader unpacks a Python runtime into `%TEMP%` on every launch,
  which is the PyInstaller behaviour antivirus flags hardest.
- **`--noupx`.** The other heuristic.
- **`--version-file`**, generated from `VERSION`. Without it the exe has no publisher string at all and SmartScreen
  has nothing to name.
- **`PrivilegesRequired=lowest`** in `packaging/pdf-helper.iss`. Per-user install, so the installer never triggers
  UAC — one less trust dialog on an unsigned build.
- **`AppId` in the `.iss` is fixed forever.** It is what makes the next version upgrade this one in place.
- **`LicenseFile=..\LICENSE`** in the `.iss` puts the MIT text on a wizard page before the install. The
  path is relative to the `.iss`, as every other path in that file is.

## Releasing

1. Bump `VERSION` — the operator's `dt patch`, not a hand edit in a feature PR.
2. Rename `## [Unreleased]` in `CHANGELOG.md` to `## [<version>] - <date>` and open a fresh `## [Unreleased]`
   above it.
3. Push a `v<version>` tag. `.github/workflows/release.yml` runs `pytest`, builds on a Windows runner and publishes
   the installer, zip and checksums as a GitHub release.

Never cut a release by copying `dist\` around. SmartScreen tracks reputation per file hash and per download source,
so a hand-copied exe starts from zero every time — and a runner build also keeps the `\\wsl.localhost` source paths
that `./build.sh` bakes in out of the shipped binary.

## Pull requests

- `pytest` green, coverage at or above 95%.
- A `CHANGELOG.md` entry under `## [Unreleased]` for anything a user would notice.
- No version bump in the diff.
- No new dependency for something a few lines of PyMuPDF or the standard library already do. `pdf2docx` alone drags
  in numpy and OpenCV and adds roughly 100 MB to the exe; that is the bar a new one has to clear.

## Licence

MIT, `Copyright (c) AragusNZ` — deliberately yearless, so there is nothing to bump. That one string in
`LICENSE` is the source; `build.ps1` stamps the same wording into the exe's `LegalCopyright` field. Contribute
under it, and do not put a personal name or a year in either place.
