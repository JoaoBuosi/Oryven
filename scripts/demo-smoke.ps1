$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== Oryven 0.17 RC1 Demo Readiness Smoke ==="
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$env:PYTHONPATH = Join-Path $root "backend"
& $python -m pytest backend/tests/test_demo_readiness_0166.py -q
if ($LASTEXITCODE -ne 0) { throw "Demo readiness backend smoke failed." }

Write-Host ""
Write-Host "Manual E2E checklist:"
Write-Host "1. Login / restore session"
Write-Host "2. Finish onboarding"
Write-Host "3. Select active project"
Write-Host "4. Confirm Home shows 'Pronto para demonstrar'"
Write-Host "5. Type or speak a supported mission"
Write-Host "6. Review one-shot authorization"
Write-Host "7. Execute and verify result"
Write-Host "8. Open Mission Intelligence / evidence"
Write-Host "9. Exercise Emergency Stop"
