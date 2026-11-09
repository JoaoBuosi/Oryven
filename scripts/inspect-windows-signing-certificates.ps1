$ErrorActionPreference='Stop'
Write-Host '=== CERTIFICADOS DE CODE SIGNING DISPONIVEIS ==='
$certs = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -ErrorAction SilentlyContinue |
  Where-Object {
    $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) -and
    ((@($_.EnhancedKeyUsageList | ForEach-Object { $_.ObjectId.Value }) -contains '1.3.6.1.5.5.7.3.3') -or
     ($_.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' } | ForEach-Object { $_.Format($false) }) -match 'Code Signing')
  } |
  Select-Object Subject, Thumbprint, NotBefore, NotAfter, HasPrivateKey
if (-not $certs) {
  Write-Warning 'Nenhum certificado de Code Signing com chave privada foi encontrado. Para distribuicao comercial, adquira/use um certificado confiavel ou um servico de Trusted Signing. Um certificado autoassinado serve apenas para testar o pipeline e nao remove alertas de confianca do Windows.'
} else {
  $certs | Format-Table -AutoSize
  Write-Host "`nDefina ORYVEN_WINDOWS_CERT_THUMBPRINT com o Thumbprint escolhido."
}
