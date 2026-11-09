# Requer setup-windows.ps1 executado primeiro. Não instala navegadores extras além do Chromium.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { throw 'Execute scripts\setup-windows.ps1 antes.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-control.txt
& '.\.venv\Scripts\python.exe' -m playwright install chromium
Write-Host 'Windows UIA e Playwright preparados. Nenhuma permissão automática foi concedida.'
