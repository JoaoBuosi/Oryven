$ErrorActionPreference = 'Stop'
$base = if ($env:ORYVEN_BUNO_API_URL) { $env:ORYVEN_BUNO_API_URL.TrimEnd('/') } else { 'http://127.0.0.1:8000' }
Write-Host '=== ORYVEN / BUNO INTEGRATION CHECK ==='
try {
    $health = Invoke-RestMethod "$base/api/v1/health" -TimeoutSec 4
    Write-Host '[OK] Buno health respondeu'
} catch {
    throw "Buno AI indisponivel em $base. Inicie a Buno e tente novamente."
}
if (-not $env:ORYVEN_BUNO_BEARER_TOKEN) {
    Write-Warning 'ORYVEN_BUNO_BEARER_TOKEN nao esta configurado. Health passou, mas planner/chat autenticado nao foi validado.'
    exit 2
}
$headers = @{ Authorization = "Bearer $env:ORYVEN_BUNO_BEARER_TOKEN" }
try {
    $me = Invoke-RestMethod "$base/api/v1/auth/me" -Headers $headers -TimeoutSec 4
    Write-Host '[OK] Token Buno aceito por /api/v1/auth/me (token nao exibido)'
} catch {
    throw 'Token Buno configurado, mas /api/v1/auth/me rejeitou ou falhou. O token nao foi exibido.'
}
Write-Host '=== BUNO CHECK CONCLUIDO ==='
