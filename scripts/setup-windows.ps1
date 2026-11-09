# Executar na raiz do projeto. Não sobrescreve .env existente.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { py -3.11 -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt -r requirements-voice.txt -r requirements-dev.txt
if (-not (Test-Path '.\.env')) { Copy-Item '.\.env.example' '.\.env' }
Push-Location web
try { npm install } finally { Pop-Location }
Write-Host 'Dependencias preparadas. Configure .env e baixe o modelo Vosk (veja README).'
