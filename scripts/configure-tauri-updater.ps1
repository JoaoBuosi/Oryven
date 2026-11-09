param(
  [Parameter(Mandatory=$true)][string]$PublicKey,
  [Parameter(Mandatory=$true)][string]$Endpoint
)
$ErrorActionPreference='Stop'
$path = Join-Path $PSScriptRoot '..\web\src-tauri\tauri.conf.json'
$config = Get-Content $path -Raw | ConvertFrom-Json
$config.bundle | Add-Member -NotePropertyName createUpdaterArtifacts -NotePropertyValue $true -Force
if(-not $config.plugins){ $config | Add-Member -NotePropertyName plugins -NotePropertyValue ([pscustomobject]@{}) }
$config.plugins | Add-Member -NotePropertyName updater -NotePropertyValue ([pscustomobject]@{
  pubkey=$PublicKey
  endpoints=@($Endpoint)
  windows=[pscustomobject]@{ installMode='passive' }
}) -Force
$config | ConvertTo-Json -Depth 20 | Set-Content $path -Encoding utf8
Write-Host 'Updater Tauri configurado. A private key NÃO foi gravada.' -ForegroundColor Green
