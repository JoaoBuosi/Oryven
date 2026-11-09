$ErrorActionPreference = 'Stop'
Write-Host '=== Oryven 0.18 Functional MVP acceptance ==='
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
python -m pytest -q backend/tests/test_functional_mvp_018.py
if ($LASTEXITCODE -ne 0) { throw 'Functional MVP acceptance tests failed.' }
Write-Host ''
Write-Host 'Automated acceptance passed.'
Write-Host 'Windows manual gate:'
Write-Host '1. Launch Oryven desktop.'
Write-Host '2. Select an active project containing an XLSX.'
Write-Host '3. Start Professional Multi-App.'
Write-Host '4. Approve report generation.'
Write-Host '5. Verify the DOCX exists.'
Write-Host '6. Approve opening the DOCX.'
Write-Host '7. Confirm Word/default associated app displays the exact report.'
Write-Host '8. Confirm Mission Intelligence contains evidence and no hidden auto-approval.'
