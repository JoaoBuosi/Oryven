$ErrorActionPreference='Stop'
$base = if($env:ORYVEN_PILOT_SERVICE_URL){$env:ORYVEN_PILOT_SERVICE_URL}else{'https://oryven-pilot-api-production.up.railway.app'}
Write-Host '=== Oryven Production Activation Status ==='
try {
  $health = Invoke-RestMethod -Uri "$base/health" -Method Get -TimeoutSec 10
  Write-Host "Pilot Service: $($health.status)" -ForegroundColor Green
  Write-Host "Stripe configured: $($health.stripe_configured)"
  Write-Host "Webhook configured: $($health.webhook_configured)"
  Write-Host "API auth configured: $($health.api_auth_configured)"
} catch {
  Write-Warning "Pilot Service indisponível: $($_.Exception.Message)"
}
Write-Host "SendGrid key: $([bool]$env:SENDGRID_API_KEY)"
Write-Host "Buno JWT: $([bool]$env:ORYVEN_BUNO_BEARER_TOKEN)"
Write-Host "Updater manifest: $([bool]$env:ORYVEN_UPDATE_MANIFEST_URL)"
