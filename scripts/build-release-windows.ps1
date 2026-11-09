$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$version = '0.19.1'
if ($env:ORYVEN_WINDOWS_CERT_THUMBPRINT) {
    & "$PSScriptRoot\validate-signed-windows-release.ps1" -CertificateThumbprint $env:ORYVEN_WINDOWS_CERT_THUMBPRINT
    exit 0
}
& "$PSScriptRoot\validate-windows-019.ps1"
$source = Get-ChildItem "$root\web\src-tauri\target\release\bundle\nsis" -Filter '*.exe' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $source) { throw 'Instalador NSIS ausente apos validacao.' }
$out = Join-Path $root 'release'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$filename = "Oryven-Setup-$version.exe"
$dest = Join-Path $out $filename
Copy-Item $source.FullName $dest -Force
$hash = (Get-FileHash $dest -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path (Join-Path $out 'SHA256SUMS.txt') -Value "$hash  $filename" -Encoding ascii
Write-Host "Release: $dest"
Write-Host "SHA256: $hash"
