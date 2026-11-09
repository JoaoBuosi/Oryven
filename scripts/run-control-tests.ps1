$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { throw 'Execute scripts\setup-windows.ps1 antes.' }
$env:PYTHONPATH = Join-Path $root 'backend'
& '.\.venv\Scripts\python.exe' -m pytest backend\tests\test_computer_control.py backend\tests\test_window_actions.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
