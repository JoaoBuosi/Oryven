$ErrorActionPreference='Stop'
Write-Host '=== Oryven 0.19.1 Production Activation ==='

if ([string]::IsNullOrWhiteSpace($env:ORYVEN_PILOT_SERVICE_URL)) {
  $env:ORYVEN_PILOT_SERVICE_URL = 'https://oryven-pilot-api-production.up.railway.app'
  Write-Host '[OK] ORYVEN_PILOT_SERVICE_URL configurada para o serviço de produção.' -ForegroundColor Green
}

$required = @('ORYVEN_PILOT_SERVICE_TOKEN','SENDGRID_API_KEY','SENDGRID_FROM_EMAIL','ORYVEN_BUNO_BEARER_TOKEN','ORYVEN_BUNO_API_URL')
foreach($name in $required){
  $v = [Environment]::GetEnvironmentVariable($name,'Process')
  if([string]::IsNullOrWhiteSpace($v)){ Write-Warning "$name não configurada" } else { Write-Host "$name OK" -ForegroundColor Green }
}

Write-Host 'Pilot Service:' $env:ORYVEN_PILOT_SERVICE_URL
Write-Host 'Nunca coloque STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET ou STRIPE_PRICE_PILOT no desktop.' -ForegroundColor Yellow
Write-Host 'Esses valores pertencem exclusivamente ao serviço remoto Railway.' -ForegroundColor Yellow
