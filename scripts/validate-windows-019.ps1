$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$expected = '0.19.1'
Write-Host '=== ORYVEN 0.19 PAID PILOT - WINDOWS RELEASE GATE ==='
Write-Host "Root: $root"

function Require-Command([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "Dependencia obrigatoria ausente: $Name" }
    Write-Host "[OK] $Name -> $($cmd.Source)"
}
function Assert-Contains([string]$Path, [string]$Needle) {
    if (-not (Test-Path $Path)) { throw "Arquivo obrigatorio ausente: $Path" }
    $raw = Get-Content -Raw -LiteralPath $Path
    if ($raw -notmatch [regex]::Escape($Needle)) { throw "Versionamento inconsistente em $Path (esperado $Needle)" }
    Write-Host "[OK] versao $expected -> $Path"
}

Require-Command 'node'
Require-Command 'npm'
Require-Command 'cargo'
Require-Command 'rustc'

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { Require-Command 'python'; $python = 'python' }
else { Write-Host "[OK] Python venv -> $python" }

Assert-Contains "$root\backend\oryven\release_info.py" $expected
Assert-Contains "$root\web\package.json" $expected
Assert-Contains "$root\web\src-tauri\Cargo.toml" $expected
Assert-Contains "$root\web\src-tauri\tauri.conf.json" $expected

# WebView2 is required by Tauri on Windows. Presence can vary by architecture, so check common registry locations.
$webViewFound = $false
$webViewKeys = @(
  'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F1E7E8D4-DC3C-4D68-A1B6-6C1B0C7D4F4B}',
  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F1E7E8D4-DC3C-4D68-A1B6-6C1B0C7D4F4B}',
  'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F1E7E8D4-DC3C-4D68-A1B6-6C1B0C7D4F4B}'
)
foreach ($key in $webViewKeys) { if (Test-Path $key) { $webViewFound = $true; break } }
if ($webViewFound) { Write-Host '[OK] WebView2 runtime detectado' }
else { Write-Warning 'WebView2 nao foi detectado pelo registro. O instalador Tauri pode instalar/usar runtime disponivel; valide manualmente no PC limpo.' }

Write-Host '--- Backend tests ---'
$env:PYTHONPATH = Join-Path $root 'backend'
& $python -m pytest "$root\backend\tests" -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests falharam.' }

Write-Host '--- Compile backend ---'
& $python -m compileall -q "$root\backend\oryven" "$root\scripts\backend_entry.py"
if ($LASTEXITCODE -ne 0) { throw 'compileall falhou.' }

Write-Host '--- Build backend sidecar ---'
& "$PSScriptRoot\build-backend.ps1"
$backendExe = Join-Path $root 'backend-dist\oryven-backend.exe'
if (-not (Test-Path $backendExe)) { throw 'Sidecar oryven-backend.exe nao foi gerado.' }

Write-Host '--- Smoke sidecar ---'
$probeData = Join-Path $env:TEMP ('oryven-0191-probe-' + [guid]::NewGuid().ToString())
$oldData = $env:ORYVEN_DATA_DIR
$env:ORYVEN_DATA_DIR = $probeData
$proc = Start-Process -FilePath $backendExe -PassThru -WindowStyle Hidden
try {
    $health = $null
    for ($i=0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 250
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2
            if ($health.status -eq 'ok') { break }
        } catch {}
    }
    if (-not $health -or $health.status -ne 'ok') { throw 'Sidecar nao respondeu ao /api/health.' }
    if ($health.version -ne $expected) { throw "Sidecar reportou versao $($health.version), esperado $expected" }
    Write-Host "[OK] Sidecar health -> $($health.version) / $($health.release_channel)"
    $log = Join-Path $probeData 'logs\oryven.log'
    if (-not (Test-Path $log)) { throw 'Log de diagnostico do sidecar nao foi criado.' }
    Write-Host '[OK] Logging local criado'
} finally {
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    if ($null -eq $oldData) { Remove-Item Env:ORYVEN_DATA_DIR -ErrorAction SilentlyContinue } else { $env:ORYVEN_DATA_DIR = $oldData }
    Remove-Item $probeData -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host '--- Frontend dependencies/build ---'
Set-Location "$root\web"
if (Test-Path 'package-lock.json') { npm ci } else { npm install }
if ($LASTEXITCODE -ne 0) { throw 'Instalacao npm falhou.' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build falhou.' }

Write-Host '--- Tauri / NSIS ---'
npm run tauri build
if ($LASTEXITCODE -ne 0) { throw 'Tauri/NSIS build falhou.' }
$nsis = Get-ChildItem "$root\web\src-tauri\target\release\bundle\nsis" -Filter '*.exe' -File -ErrorAction Stop | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $nsis) { throw 'Instalador NSIS nao encontrado.' }
$hash = (Get-FileHash $nsis.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "[OK] Instalador: $($nsis.FullName)"
Write-Host "[OK] SHA256: $hash"
Write-Host '=== ORYVEN 0.19.1 PRODUCTION ACTIVATION GATE CONCLUIDO ==='
