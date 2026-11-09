$ErrorActionPreference = 'Stop'
Write-Host '=== Oryven 0.19 Paid Pilot acceptance ==='
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = Join-Path $root 'backend'
python -m pytest -q backend/tests/test_paid_pilot_019.py backend/tests/test_functional_mvp_018.py backend/tests/test_release_candidate.py
if ($LASTEXITCODE -ne 0) { throw 'Paid Pilot acceptance failed.' }
python -m compileall -q backend/oryven
if ($LASTEXITCODE -ne 0) { throw 'Backend compile failed.' }
Write-Host 'Backend Paid Pilot gates passed.' -ForegroundColor Green
Write-Host 'Windows product gates still required: npm build, Tauri/NSIS, license activation, Terms/Privacy UI, export, account deletion, Buno, microphone/voice, clean PC.' -ForegroundColor Yellow
