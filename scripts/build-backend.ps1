$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python -m pip install pyinstaller
Remove-Item "$root\backend-dist" -Recurse -Force -ErrorAction SilentlyContinue
& $python -m PyInstaller --noconfirm --clean --onefile --name oryven-backend --paths "$root\backend" "$root\scripts\backend_entry.py" --collect-submodules oryven --distpath "$root\backend-dist" --workpath "$root\build\pyinstaller" --specpath "$root\build"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }
Write-Host "Backend criado em $root\backend-dist\oryven-backend.exe"
