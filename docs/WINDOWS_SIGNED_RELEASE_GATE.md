# Oryven 0.19.1 — Windows Signed Release Gate

## Objetivo

Validar um instalador Windows distribuível do Oryven com:

- NSIS `.exe` e MSI `.msi` gerados no Windows;
- assinatura Authenticode válida com certificado de Code Signing que possua chave privada;
- digest SHA-256 e timestamp;
- verificação dupla com `Get-AuthenticodeSignature` e `signtool verify /pa /all`;
- hash SHA-256 dos artefatos finais;
- opcionalmente instalação silenciosa, abertura do aplicativo, health do sidecar e desinstalação.

## Pré-requisitos

- Windows 10/11;
- Node/npm;
- Rust/Cargo MSVC;
- Microsoft C++ Build Tools;
- WebView2;
- VBSCRIPT habilitado para gerar MSI;
- certificado de Code Signing confiável instalado em `CurrentUser\\My` ou `LocalMachine\\My`, com chave privada acessível.

## 1. Descobrir o certificado

```powershell
.\\scripts\\inspect-windows-signing-certificates.ps1
```

Depois, somente no seu Windows:

```powershell
$env:ORYVEN_WINDOWS_CERT_THUMBPRINT = '<THUMBPRINT>'
```

Não envie PFX, senha ou chave privada para GitHub, frontend, logs ou conversa.

## 2. Build + assinatura + verificação

```powershell
.\\scripts\\validate-signed-windows-release.ps1
```

## 3. Gate completo, incluindo instalação

Execute em uma máquina sem Oryven instalado:

```powershell
.\\scripts\\validate-signed-windows-release.ps1 -InstallSmoke
```

Esse fluxo instala silenciosamente o NSIS, localiza o `oryven.exe`, verifica a assinatura do app instalado, inicia o app, exige `/api/health` 0.19.1 e desinstala ao final.

## Saída esperada

```text
release/windows-signed/
  OryvenSetup-0.19.1.exe
  Oryven-0.19.1-x64.msi
  SHA256SUMS.txt
```

O gate somente imprime `SIGNED WINDOWS RELEASE: PASS` depois de validar assinatura dos dois instaladores. Com `-InstallSmoke`, também precisa provar instalação, execução e desinstalação.

## Importante

Uma assinatura autoassinada pode provar que o pipeline técnico funciona, mas não equivale a uma assinatura comercial confiável para usuários externos e não garante ausência de avisos do SmartScreen. Para distribuição comercial, use certificado/serviço de assinatura confiável e mantenha a chave privada fora do repositório.
