param(
  [string]$CertificateThumbprint = $env:ORYVEN_WINDOWS_CERT_THUMBPRINT,
  [string]$TimestampUrl = $(if ($env:ORYVEN_TIMESTAMP_URL) { $env:ORYVEN_TIMESTAMP_URL } else { 'http://timestamp.digicert.com' }),
  [switch]$TimestampTsp,
  [switch]$InstallSmoke,
  [switch]$KeepInstalled
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$expected = '0.19.1'
$configPath = Join-Path $root 'web\src-tauri\tauri.conf.json'
$backupPath = "$configPath.oryven-signing-backup"

function Require-Command([string]$Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $cmd) { throw "Dependencia obrigatoria ausente: $Name" }
  Write-Host "[OK] $Name -> $($cmd.Source)"
  return $cmd
}

function Get-SigningCertificate([string]$Thumbprint) {
  if (-not $Thumbprint) {
    throw 'Defina ORYVEN_WINDOWS_CERT_THUMBPRINT com o SHA1/thumbprint de um certificado de Code Signing confiavel que tenha chave privada.'
  }
  $normalized = ($Thumbprint -replace '\s','').ToUpperInvariant()
  $cert = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -ErrorAction SilentlyContinue |
    Where-Object { ($_.Thumbprint -replace '\s','').ToUpperInvariant() -eq $normalized } |
    Select-Object -First 1
  if (-not $cert) { throw "Certificado $normalized nao encontrado em CurrentUser/My ou LocalMachine/My." }
  if (-not $cert.HasPrivateKey) { throw 'O certificado encontrado nao possui chave privada acessivel.' }
  if ($cert.NotAfter -le (Get-Date)) { throw "Certificado expirado em $($cert.NotAfter)." }
  $eku = @($cert.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' } | ForEach-Object { $_.Format($false) }) -join '; '
  if ($eku -and $eku -notmatch 'Code Signing|1\.3\.6\.1\.5\.5\.7\.3\.3') {
    throw 'O certificado nao anuncia EKU de Code Signing.'
  }
  Write-Host "[OK] Certificado -> $($cert.Subject)"
  Write-Host "[OK] Thumbprint   -> $($cert.Thumbprint)"
  Write-Host "[OK] Validade     -> $($cert.NotBefore) ate $($cert.NotAfter)"
  return $cert
}

function Assert-Authenticode([string]$Path, [string]$ExpectedThumbprint) {
  if (-not (Test-Path -LiteralPath $Path)) { throw "Artefato ausente: $Path" }
  $sig = Get-AuthenticodeSignature -LiteralPath $Path
  if ($sig.Status -ne 'Valid') {
    throw "Assinatura Authenticode invalida em $Path. Status=$($sig.Status); Mensagem=$($sig.StatusMessage)"
  }
  if (-not $sig.SignerCertificate) { throw "SignerCertificate ausente em $Path" }
  $actual = ($sig.SignerCertificate.Thumbprint -replace '\s','').ToUpperInvariant()
  $expectedNormalized = ($ExpectedThumbprint -replace '\s','').ToUpperInvariant()
  if ($actual -ne $expectedNormalized) {
    throw "Thumbprint inesperado em $Path. Obtido=$actual esperado=$expectedNormalized"
  }
  Write-Host "[OK] Authenticode VALID -> $Path"
  Write-Host "     Signer: $($sig.SignerCertificate.Subject)"
  if ($sig.TimeStamperCertificate) {
    Write-Host "     Timestamp signer: $($sig.TimeStamperCertificate.Subject)"
  } else {
    Write-Warning "Nao foi possivel ler certificado de timestamp em $Path. Verifique signtool /pa /all."
  }
}

function Find-SignTool {
  $direct = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($direct) { return $direct.Source }
  $roots = @(
    "$env:ProgramFiles(x86)\Windows Kits\10\bin",
    "$env:ProgramFiles\Windows Kits\10\bin"
  ) | Where-Object { $_ -and (Test-Path $_) }
  $candidate = foreach ($r in $roots) {
    Get-ChildItem $r -Recurse -Filter signtool.exe -File -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' }
  }
  return ($candidate | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}

function Verify-WithSignTool([string]$SignTool, [string]$Path) {
  if (-not $SignTool) { Write-Warning 'signtool.exe nao encontrado; Get-AuthenticodeSignature continua sendo obrigatorio.'; return }
  & $SignTool verify /pa /all /v $Path
  if ($LASTEXITCODE -ne 0) { throw "signtool verify falhou para $Path" }
  Write-Host "[OK] signtool verify /pa /all -> $Path"
}

function Get-OryvenInstallEntry {
  $keys = @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
  )
  return Get-ItemProperty $keys -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like 'Oryven*' } |
    Sort-Object InstallDate -Descending |
    Select-Object -First 1
}

function Find-InstalledOryvenExe {
  $entry = Get-OryvenInstallEntry
  $candidates = @()
  if ($entry.InstallLocation) {
    $candidates += (Join-Path $entry.InstallLocation 'oryven.exe')
    $candidates += (Join-Path $entry.InstallLocation 'Oryven.exe')
  }
  $candidates += "$env:LOCALAPPDATA\Oryven by Buno AI\oryven.exe"
  $candidates += "$env:LOCALAPPDATA\Programs\Oryven by Buno AI\oryven.exe"
  $existing = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
  if ($existing) { return $existing }
  return Get-ChildItem $env:LOCALAPPDATA -Filter oryven.exe -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "$root*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 -ExpandProperty FullName
}

Write-Host '=== ORYVEN SIGNED WINDOWS RELEASE VALIDATION ==='
Write-Host "Root: $root"
Require-Command 'node' | Out-Null
Require-Command 'npm' | Out-Null
Require-Command 'cargo' | Out-Null
Require-Command 'rustc' | Out-Null
$cert = Get-SigningCertificate $CertificateThumbprint
$signTool = Find-SignTool
if ($signTool) { Write-Host "[OK] signtool -> $signTool" } else { Write-Warning 'Windows SDK signtool.exe nao localizado.' }

# MSI needs Windows + WiX/VBSCRIPT. Tauri downloads WiX tooling, but VBSCRIPT must be enabled.
$vb = Get-WindowsOptionalFeature -Online -FeatureName VBSCRIPT -ErrorAction SilentlyContinue
if ($vb -and $vb.State -eq 'Disabled') {
  throw 'VBSCRIPT esta desabilitado. Habilite o recurso opcional do Windows antes de gerar MSI.'
}
if ($vb) { Write-Host "[OK] VBSCRIPT -> $($vb.State)" }

# Run the existing regression/sidecar/frontend gates before the signed bundle build.
& "$PSScriptRoot\validate-windows-019.ps1"

Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
try {
  $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
  $config.bundle.targets = @('nsis','msi')
  $config.bundle | Add-Member -NotePropertyName publisher -NotePropertyValue 'Buno AI' -Force
  if (-not $config.bundle.windows) {
    $config.bundle | Add-Member -NotePropertyName windows -NotePropertyValue ([pscustomobject]@{})
  }
  $config.bundle.windows | Add-Member -NotePropertyName certificateThumbprint -NotePropertyValue $cert.Thumbprint -Force
  $config.bundle.windows | Add-Member -NotePropertyName digestAlgorithm -NotePropertyValue 'sha256' -Force
  $config.bundle.windows | Add-Member -NotePropertyName timestampUrl -NotePropertyValue $TimestampUrl -Force
  $config.bundle.windows | Add-Member -NotePropertyName tsp -NotePropertyValue ([bool]$TimestampTsp) -Force
  $config.bundle.windows | Add-Member -NotePropertyName webviewInstallMode -NotePropertyValue ([pscustomobject]@{ type='downloadBootstrapper'; silent=$true }) -Force
  $config | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $configPath -Encoding utf8

  Set-Location "$root\web"
  Write-Host '--- Signed Tauri build: NSIS + MSI ---'
  npm run tauri build
  if ($LASTEXITCODE -ne 0) { throw 'Tauri signed build falhou.' }
} finally {
  if (Test-Path -LiteralPath $backupPath) {
    Move-Item -LiteralPath $backupPath -Destination $configPath -Force
  }
}

$nsis = Get-ChildItem "$root\web\src-tauri\target\release\bundle\nsis" -Filter '*.exe' -File -ErrorAction Stop |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
$msi = Get-ChildItem "$root\web\src-tauri\target\release\bundle\msi" -Filter '*.msi' -File -ErrorAction Stop |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $nsis) { throw 'NSIS .exe nao foi gerado.' }
if (-not $msi) { throw 'MSI nao foi gerado.' }

Assert-Authenticode $nsis.FullName $cert.Thumbprint
Assert-Authenticode $msi.FullName $cert.Thumbprint
Verify-WithSignTool $signTool $nsis.FullName
Verify-WithSignTool $signTool $msi.FullName

$out = Join-Path $root 'release\windows-signed'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$exeDest = Join-Path $out "OryvenSetup-$expected.exe"
$msiDest = Join-Path $out "Oryven-$expected-x64.msi"
Copy-Item $nsis.FullName $exeDest -Force
Copy-Item $msi.FullName $msiDest -Force
Assert-Authenticode $exeDest $cert.Thumbprint
Assert-Authenticode $msiDest $cert.Thumbprint

$hashes = @(
  "$( (Get-FileHash $exeDest -Algorithm SHA256).Hash.ToLowerInvariant() )  $(Split-Path $exeDest -Leaf)",
  "$( (Get-FileHash $msiDest -Algorithm SHA256).Hash.ToLowerInvariant() )  $(Split-Path $msiDest -Leaf)"
)
Set-Content -LiteralPath (Join-Path $out 'SHA256SUMS.txt') -Value $hashes -Encoding ascii

if ($InstallSmoke) {
  Write-Host '--- NSIS silent install smoke ---'
  $existing = Get-OryvenInstallEntry
  if ($existing) { throw 'Ja existe uma instalacao Oryven registrada. Desinstale-a antes do smoke automatizado.' }
  $install = Start-Process -FilePath $exeDest -ArgumentList '/S' -PassThru -Wait
  if ($install.ExitCode -ne 0) { throw "NSIS /S falhou. ExitCode=$($install.ExitCode)" }
  Start-Sleep -Seconds 2
  $appExe = Find-InstalledOryvenExe
  if (-not $appExe) { throw 'Instalacao terminou, mas oryven.exe instalado nao foi localizado.' }
  Write-Host "[OK] App instalado -> $appExe"
  Assert-Authenticode $appExe $cert.Thumbprint
  Verify-WithSignTool $signTool $appExe

  $app = Start-Process -FilePath $appExe -PassThru
  try {
    $health = $null
    for ($i=0; $i -lt 60; $i++) {
      Start-Sleep -Milliseconds 500
      try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2
        if ($health.status -eq 'ok') { break }
      } catch {}
    }
    if (-not $health -or $health.status -ne 'ok') { throw 'O app instalado abriu, mas o backend sidecar nao respondeu ao health.' }
    if ($health.version -ne $expected) { throw "Health instalado reportou $($health.version), esperado $expected" }
    Write-Host "[OK] Installed runtime health -> $($health.version) / $($health.release_channel)"
  } finally {
    if ($app -and -not $app.HasExited) { Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue }
    Get-Process oryven-backend -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  }

  if (-not $KeepInstalled) {
    $entry = Get-OryvenInstallEntry
    if (-not $entry -or -not $entry.UninstallString) { throw 'Nao foi possivel localizar o desinstalador depois do smoke.' }
    $uninstall = $entry.UninstallString.Trim('"')
    Write-Host "--- Silent uninstall -> $uninstall ---"
    $un = Start-Process -FilePath $uninstall -ArgumentList '/S' -PassThru -Wait
    if ($un.ExitCode -ne 0) { throw "Desinstalacao silenciosa falhou. ExitCode=$($un.ExitCode)" }
    Write-Host '[OK] Instalacao e desinstalacao silenciosas validadas.'
  }
}

Write-Host '=== SIGNED WINDOWS RELEASE: PASS ===' -ForegroundColor Green
Write-Host "NSIS: $exeDest"
Write-Host "MSI : $msiDest"
Write-Host "SHA : $(Join-Path $out 'SHA256SUMS.txt')"
