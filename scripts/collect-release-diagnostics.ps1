$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $root "release-diagnostics-$stamp"
New-Item -ItemType Directory -Path $out -Force | Out-Null
$lines = @()
$lines += "timestamp=$(Get-Date -Format o)"
$lines += "os=$([Environment]::OSVersion.VersionString)"
foreach ($name in @('python','node','npm','cargo','rustc')) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  $lines += "$name=" + $(if ($cmd) { $cmd.Source } else { 'missing' })
}
$lines += "buno_url_configured=$([bool]$env:ORYVEN_BUNO_API_URL)"
$lines += "buno_token_configured=$([bool]$env:ORYVEN_BUNO_BEARER_TOKEN)"
$lines += "elevenlabs_configured=$([bool]$env:ELEVENLABS_API_KEY)"
$lines += "vosk_model_configured=$([bool]$env:ORYVEN_VOSK_MODEL)"
$lines | Set-Content (Join-Path $out 'environment.txt') -Encoding utf8
$data = if ($env:ORYVEN_DATA_DIR) { $env:ORYVEN_DATA_DIR } else { Join-Path $HOME '.oryven-mvp' }
$log = Join-Path $data 'logs\oryven.log'
$crash = Join-Path $data 'logs\last_crash.json'
if (Test-Path $log) { Get-Content $log -Tail 500 | Set-Content (Join-Path $out 'oryven-log-tail.txt') -Encoding utf8 }
if (Test-Path $crash) { Copy-Item $crash (Join-Path $out 'last_crash.json') }
Write-Host "Diagnostico criado em: $out"
Write-Host 'Nenhum token, senha ou API key foi copiado.'
