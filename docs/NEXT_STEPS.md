# Próximas etapas após Computer Control 0.4

Validação Windows real: instalar dependências, verificar UIA Notepad, Playwright Chromium, ElevenLabs, Vosk e Buno API; compilar React/Tauri; executar demonstração manual. Depois automatizar ações reversíveis com escopo de janela e verificação antes/depois.

# Plano incremental Oryven by Buno AI

## M0 (entregue na 0.2)
- Abertura de pesquisa web e apps allowlist, aprovação de uso único, Vosk local, ElevenLabs TTS.
- Ambiente-alvo Windows 10/11. Ainda faltam testes E2E no Windows.

## M1 (entregue no código 0.3; validação Windows pendente)
- Oryven Missions 1–3 etapas conhecidas, persistência SQLite, pausa, cancelamento, validação humana.
- Interface React/Tauri com visualizador de plano e botões de controle.
- 24 testes backend passando em ambiente sem Windows.

## M2 (próxima implementação depois da validação do ambiente)
- Corrigir o bootstrap da sessão: substituir token publicável no loopback por canal confiável Tauri + sidecar.
- Observação por janela: usar Windows UI Automation em modo leitura com consentimento e evidências de verificadores.
- Provar estado de janela/app após comandos; não usar apenas confirmação do Popen/webbrowser.
- Smoke tests no Windows 10 e 11; latência Vosk/ElevenLabs.
- Distribuição instalável sidecar empacotado e instalador assinado em fase apropriada.

## M3 (dependente do M2)
- Buno Intelligence: adaptador de modelo por interfaces separadas, com retorno estritamente tipado.
- Buno Forge: concessões por ação, auditoria e revogação, sem autoelevação de permissões.
- UI Automation Windows, Playwright para navegador autorizado; observação sem vigilância contínua.
- Skills com entradas e saídas JSON schema, assinaturas/instalação verificável.

## M4 (produto)
- Developer: VS Code, inspeção/read-only de repositório, branch e diffs reversíveis; push e deploy apenas com aprovação.
- Studio: discovery Maya, plugin Maya Python/MEL, consulta de cenas em modo leitura, edições apenas com confirmação.
- Planos comerciais depois de autenticação real, controle de quotas, cobrança e proteção dos segredos.

## Ordem de validação no Windows ao chegar em casa

1. `./scripts/diagnose-windows.ps1` (no PowerShell, usar ` .\\scripts\\diagnose-windows.ps1`)
2. ` .\\scripts\\setup-windows.ps1` para instalar dependências, se necessário.
3. Configurar `.env` sem compartilhar a API key; baixar modelo Vosk.
4. Backend: ` .\\scripts\\run-backend.ps1`; frontend: `cd web; npm run dev`.
5. Teste somente texto: criar missão de 2 passos, autorizar cada ação e confirmar manualmente.
6. Teste de voz: habilitar microfone e dizer a frase de ativação, autorizar na interface e escutar resposta.
7. Rodar ` .\\scripts\\run-tests.ps1` para Python e build frontend; `npm run tauri dev` só depois de instalar Rust e dependências Tauri.

**Verificações não realizadas na criação deste pacote:** automação real do Windows, som físico, resposta real da ElevenLabs, Tauri build e instalador Windows.
