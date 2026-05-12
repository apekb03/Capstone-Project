# Build a distributable folder: dist\HeartBeatDevil\
# Run on Windows only. Zip that folder → upload as GitHub Release asset (e.g. HeartBeatDevil-windows.zip).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

python -m pip install -r requirements-build.txt
pyinstaller --noconfirm --clean HeartBeatDevil.spec

Write-Host ""
Write-Host "Built: $Root\dist\HeartBeatDevil\"
Write-Host "Zip the HeartBeatDevil folder and upload as a Release asset."
