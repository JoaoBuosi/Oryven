# Diagnóstico somente leitura para Oryven, sem exibir credenciais.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Write-Host "=== ORYVEN - diagnostico Windows ==="
Write-Host "Pasta: $root"
Write-Host "Sistema: $([Environment]::OSVersion.VersionString)"
function Check-Command([string]$Name, [string[]]$Arguments) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) { Write-Host "[AUSENTE] $Name"; return }
    Write-Host "[ENCONTRADO] $Name"
    & $Name @Arguments 2>&1 | Select-Object -First 2
}
Check-Command 'py' @('-3.11','--version')
Check-Command 'node' @('--version')
Check-Command 'npm' @('--version')
Check-Command 'cargo' @('--version')
Write-Host ("[VENV] " + (Test-Path (Join-Path $root '.venv\Scripts\python.exe')))
Write-Host ("[NODE MODULES] " + (Test-Path (Join-Path $root 'web\node_modules')))
Write-Host ("[.ENV] " + (Test-Path (Join-Path $root '.env')) + ' (conteudo oculto)')
Write-Host ("[VOSK DEFAULT] " + (Test-Path 'C:\modelos\vosk-model-small-pt-0.3'))
Write-Host 'Diagnostico finalizado. Nenhuma chave da ElevenLabs foi impressa.'
