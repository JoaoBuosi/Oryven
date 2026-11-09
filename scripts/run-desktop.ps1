$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath (Join-Path $root 'web')
# Backend Python deve estar rodando em outro terminal.
npm run tauri dev
