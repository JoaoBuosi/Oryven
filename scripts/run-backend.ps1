$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = (Join-Path $root 'backend')
& '.\.venv\Scripts\python.exe' -m oryven
