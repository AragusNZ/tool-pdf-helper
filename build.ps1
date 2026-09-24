# Builds dist\PdfHelper\PdfHelper.exe, then dist\PdfHelper-<version>.zip + .sha256.
# Needs Windows Python 3 (py launcher). From WSL run ./build.sh - it uses the Windows Python over \\wsl.localhost.
# The venv and PyInstaller work dir live under %LOCALAPPDATA%\pdf-helper: pip over \\wsl.localhost is unusably slow.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$work = Join-Path $env:LOCALAPPDATA 'pdf-helper'
$py = "$work\venv\Scripts\python.exe"
if (-not (Test-Path $py)) { py -3 -m venv "$work\venv" }
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r requirements.txt -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }

$version = (Get-Content "$PSScriptRoot\VERSION" -Raw).Trim()
$name = 'PdfHelper'

# Asset paths are absolute: a relative --add-data/--icon resolves against --specpath, which is outside the repo.
& $py -m PyInstaller --noconfirm --clean --onefile --windowed --name $name --collect-submodules pymupdf_fonts --icon "$PSScriptRoot\pdf_helper\assets\icon.ico" `
    --add-data "$PSScriptRoot\pdf_helper\assets;pdf_helper\assets" --add-data "$PSScriptRoot\VERSION;." --workpath "$work\build" --specpath "$work" pdf_helper\__main__.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }

$stage = "dist\$name"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item $stage -ItemType Directory | Out-Null
Copy-Item "dist\$name.exe", 'README.md' $stage

$zip = "dist\$name-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "$stage\*" -DestinationPath $zip
(Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() + "  $name-$version.zip" | Set-Content "$zip.sha256"
Write-Host "Built $zip"
