$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = (Join-Path $root 'backend')
& '.\.venv\Scripts\python.exe' -m pytest backend\tests -q
Push-Location web
try { npm run build } finally { Pop-Location }
