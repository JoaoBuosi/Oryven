# Arquitetura técnica — Oryven 0.4

Leia também `COMPUTER_CONTROL.md` e `BUNO_INTEGRATION.md`.

## Componentes 0.4

```text
React / Tauri → FastAPI loopback + sessão de desenvolvimento
    → OryvenCore (roteador determinístico, permissões exatas, auditoria)
        → pywinauto Windows UIA (metadados rasos; requer autorização)
        → Playwright Chromium isolado (sites públicos permitidos)
        → BunoHealthBridge (health e chat SSE com JWT, somente texto)
        → executores 0.3 (pesquisa padrão, aplicativos Windows conhecidos)
        → missões SQLite, Vosk, ElevenLabs / fala Windows
```

# Arquitetura técnica — Oryven 0.3

## Componentes e fronteiras

```text
React/Tauri (interface local)
    | HTTP loopback + token efêmero (somente desenvolvimento)
FastAPI local /api/*
    | \-- core: detecta intenção EXPLÍCITA, sem LLM executável
    | \-- approval store: escopo + parâmetros + expiração + uso único
    | \-- missions SQLite: plano determinístico, retomada, confirmação manual
    | \-- executor: allowlist browser.search, app.launch
    | \-- audit SQLite (metadados, sem transcrições)
    | \-- listener Vosk (microfone desativado por padrão)
    | \-- ElevenLabs HTTPS TTS / voz local Windows
    | \-- registry manifests JSON (apenas leitura)
```

## Design de extensibilidade

Separar: (1) Percepção: áudio, tela, arquivos consentidos. (2) Interpretação: parser ou modelo da Buno. (3) Planejamento: tarefas tipadas com pré/pós-condições. (4) Governança: diffs de parâmetros e autorização. (5) Execução: adaptadores restritos. (6) Verificação e relato. NENHUM resultado de LLM, página ou documento vira permissão. Cada etapa da missão deve ser reconciliada no gateway de governança.

### Contratos planejados (ainda não ativos)

- `TextModel`: Ollama local / Buno / remoto. Preserva identificador do provedor e modelos, custos e contexto.
- `Planner`: propostas de passos estruturados, sem privilégio para executá-los.
- `Skill`: id+versão+entradas+saídas+permissões+validação+testes+logs; contratos declarativos em `skills/`.
- `Agent`: especialistas selecionados sob demanda, não processos permanentes.
- `Mission` 0.3: `planned -> awaiting_approval -> executing -> awaiting_verification -> confirmed_by_user -> next step`; persistência, pausa e cancelamento. Verificação é manual. Futuro: verificador por janela/DOM e revisão supervisionada.
- `WindowsComputerAdapter`: Uia/Win32 e visão computacional com escopos de janela; APIs oficiais como primeira escolha.

## Integração Buno

Oryven é um produto independente, cliente do Buno Intelligence e Buno Forge. **Não copiar e colar** serviços sem auditoria de versão e contrato. Para Oryven Studio, o Maya deverá expor um plugin Python/MEL no contexto do processo do Maya, com canal autenticado e comandos declarativos e reversíveis.

## Riscos e requisitos de produção

Sessões, rate limits e escopos por usuário, auditoria com retenção configurável, criptografia de segredos via Windows Credential Manager, sidecar assinado, atualizações assinadas, conta e billing, análise de prompt injection, integração contínua e testes Windows E2E. Nada disso deve ser presumido implementado no MVP.
