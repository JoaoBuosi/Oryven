$ErrorActionPreference = 'Stop'
if (-not $env:SENDGRID_API_KEY) { throw 'SENDGRID_API_KEY não configurada.' }
if (-not $env:SENDGRID_FROM_EMAIL) { throw 'SENDGRID_FROM_EMAIL não configurada.' }
$to = Read-Host 'E-mail de destino para teste SendGrid'
$fromName = $env:SENDGRID_FROM_NAME
if([string]::IsNullOrWhiteSpace($fromName)){ $fromName='Oryven by Buno AI' }
$headers = @{ Authorization = "Bearer $($env:SENDGRID_API_KEY)"; 'Content-Type'='application/json' }
$payload = @{
  personalizations = @(@{ to = @(@{ email = $to }); subject = 'Oryven — teste de e-mail' })
  from = @{ email = $env:SENDGRID_FROM_EMAIL; name = $fromName }
  content = @(@{ type='text/plain'; value='SendGrid do Oryven está configurado e operacional.' })
} | ConvertTo-Json -Depth 8
Invoke-RestMethod -Method Post -Uri 'https://api.sendgrid.com/v3/mail/send' -Headers $headers -Body $payload
Write-Host 'SendGrid aceitou o envio.' -ForegroundColor Green
