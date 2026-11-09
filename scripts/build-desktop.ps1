$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
& "$PSScriptRoot\build-backend.ps1"
Set-Location "$root\web"
npm install
npm run build
npm run tauri build
if ($LASTEXITCODE -ne 0) { throw "Build Tauri falhou" }
Write-Host "Build desktop concluído. Confira web\src-tauri\target\release\bundle\nsis"
