# Oryven 0.12.0 — Voice-first + Tauri Desktop

## Entregas

- Perfil de voz persistente em `voice_profile.json`.
- Nome personalizado do assistente e wake phrase `<nome>, acordar`.
- Compatibilidade histórica com Oryven/Oriven/Ori Ven para o nome padrão.
- Saudação falada na inicialização, configurável.
- Escuta em segundo plano somente após opt-in persistido.
- Endpoint para interromper fala sem cancelar aprovações.
- Abertura por voz de aplicativos descobertos no inventário universal.
- Tauri 2 com bandeja do sistema; fechar a janela oculta em vez de encerrar.
- Lifecycle do backend: sidecar `oryven-backend.exe` em produção e Python local no desenvolvimento.
- Scripts para gerar o backend com PyInstaller e o instalador NSIS com Tauri.
- Retry de conexão do frontend durante o boot do backend.

## Segurança e privacidade

Voice-first não significa microfone oculto. `background_listening_enabled` começa desativado e só é persistido quando o usuário opta por ativá-lo. Wake word e STT são processados localmente pelo runtime Vosk existente. ElevenLabs continua opcional; quando habilitado, somente o texto da resposta é enviado para a API fixa do provedor.

Preferências de voz não concedem permissões de computador, skills ou agentes. Todas as ações com efeito continuam no ApprovalStore one-shot.

## Build Windows

```powershell
.\scripts\build-desktop.ps1
```

O script:
1. gera `backend-dist\oryven-backend.exe` com PyInstaller;
2. instala dependências web;
3. executa o build React/Vite;
4. executa `tauri build` para gerar o NSIS.

O instalador final fica sob `web\src-tauri\target\release\bundle\nsis`.

## Gates ainda necessários no Windows

- instalar e validar o modelo Vosk pt-BR;
- confirmar microfone real e wake word com diferentes nomes;
- confirmar voz SAPI instalada;
- testar ElevenLabs somente com credencial local do usuário;
- compilar Rust/Tauri (Rust não está disponível no ambiente de CI usado nesta entrega);
- testar NSIS em um Windows limpo;
- validar assinatura de código e auto-update antes de distribuição comercial.
