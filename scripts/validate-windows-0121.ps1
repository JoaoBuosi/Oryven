$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Write-Host '=== ORYVEN 0.12.1 / 0.13 - WINDOWS RELEASE GATE ==='
Write-Host "Root: $root"

function Require-Command([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "Dependencia obrigatoria ausente: $Name" }
    Write-Host "[OK] $Name -> $($cmd.Source)"
}

Require-Command 'node'
Require-Command 'npm'
Require-Command 'cargo'

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { Require-Command 'python'; $python = 'python' }
else { Write-Host "[OK] Python venv -> $python" }

Write-Host '--- Backend tests ---'
$env:PYTHONPATH = Join-Path $root 'backend'
& $python -m pytest "$root\backend\tests" -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests falharam.' }

Write-Host '--- Build backend sidecar ---'
& "$PSScriptRoot\build-backend.ps1"
$backendExe = Join-Path $root 'backend-dist\oryven-backend.exe'
if (-not (Test-Path $backendExe)) { throw 'Sidecar oryven-backend.exe nao foi gerado.' }

Write-Host '--- Smoke sidecar ---'
$probeData = Join-Path $env:TEMP ('oryven-release-probe-' + [guid]::NewGuid().ToString())
$oldData = $env:ORYVEN_DATA_DIR
$env:ORYVEN_DATA_DIR = $probeData
$proc = Start-Process -FilePath $backendExe -PassThru -WindowStyle Hidden
try {
    $ok = $false
    for ($i=0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 250
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2
            if ($health.status -eq 'ok') { $ok = $true; break }
        } catch {}
    }
    if (-not $ok) { throw 'Sidecar nao respondeu ao /api/health.' }
    Write-Host "[OK] Sidecar health -> $($health.version)"
} finally {
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    if ($null -eq $oldData) { Remove-Item Env:ORYVEN_DATA_DIR -ErrorAction SilentlyContinue } else { $env:ORYVEN_DATA_DIR = $oldData }
    Remove-Item $probeData -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host '--- Frontend + Tauri ---'
Set-Location "$root\web"
npm install
if ($LASTEXITCODE -ne 0) { throw 'npm install falhou.' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build falhou.' }
npm run tauri build
if ($LASTEXITCODE -ne 0) { throw 'Tauri/NSIS build falhou.' }

$nsis = Get-ChildItem "$root\web\src-tauri\target\release\bundle\nsis" -Filter '*.exe' -File -ErrorAction Stop | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $nsis) { throw 'Instalador NSIS nao encontrado.' }
$hash = (Get-FileHash $nsis.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "[OK] Instalador: $($nsis.FullName)"
Write-Host "[OK] SHA256: $hash"
Write-Host '=== RELEASE GATE CONCLUIDO ==='
