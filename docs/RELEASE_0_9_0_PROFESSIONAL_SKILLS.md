# Oryven 0.9.0 — Professional Skills Runtime

## Objetivo

Transformar o catálogo de agentes profissionais da 0.8.0 em uma plataforma que recomenda e propõe skills concretas sem transformar seleção de agente em permissão de execução.

## Arquitetura

```text
Voz / texto / UI
       |
       v
Professional Agent Router
       |
       v
Professional Plan (sem efeitos)
       |
       +------> Skill Catalog (38 skills nesta build)
                       |
                       v
               Skill Intent Adapter
                       |
                       v
               ApprovalStore one-shot
                       |
              +--------+---------+
              |                  |
              v                  v
      Universal Work Runtime   Developer Runtime
      files + terminal         git/test/build/deploy
              |                  |
              +--------+---------+
                       v
                  Audit + result
```

## Implementado

- `SkillCatalog` carregado exclusivamente de manifests empacotados.
- `POST /api/skills/{skill_id}/propose` constrói intents tipadas; não executa sem aprovação.
- `WorkRuntime` com operações:
  - `filesystem.list`
  - `filesystem.read`
  - `filesystem.write_text`
  - `filesystem.append_text`
  - `filesystem.mkdir`
  - `terminal.run`
- filesystem confinado a `ORYVEN_WORK_ROOTS`.
- proteção contra `../`/escape por resolução canônica.
- leitura limitada a UTF-8, 1 MB, sem binários.
- escrita substitutiva atômica no mesmo diretório quando suportada.
- terminal com `shell=False`, executável allowlisted, argv exato e timeout.
- conteúdo gravado não aparece na descrição da aprovação; o fingerprint continua vinculado ao conteúdo exato.
- agentes profissionais agora retornam `recommended_skills`.
- skills planejadas para Office, Maya, design, analytics, CRM, suporte, ERP, banco de dados, datasets e knowledge não fingem execução: `executable=false`.
- frontend passa a mostrar Professional Agent Runtime e plano de skills sem efeitos colaterais.

## Segurança

Selecionar um agente nunca concede permissões. Recomendar uma skill nunca executa a skill. Uma proposta cria uma autorização one-shot vinculada a todos os parâmetros exatos. Reinício, expiração, negação ou uso anterior invalidam a autorização.

`terminal.run` não usa shell e o executável é validado por allowlist, mas ainda é uma capacidade poderosa. Deve permanecer sob aprovação explícita e roots configurados.

## Validação nesta build

- `python -m compileall backend/oryven`: OK.
- suíte backend: `96 passed`.
- testes novos cobrem path escape, binário/tamanho, read/write/list, terminal allowlist, skill adapters, approval one-shot, conteúdo oculto na descrição, agent-to-skills e APIs.
- build React/Vite não foi concluído neste ambiente porque `npm install` não terminou dentro da janela disponível. Validar localmente no Windows com `npm install` e `npm run build`.

## Próximos marcos

### 0.10 — Universal Computer Operator
- inventário confiável de apps;
- seleção e foco de apps conhecidos;
- UIA com campos, menus, listas e verificação de estado;
- Playwright com interações governadas;
- camada de percepção/visão para interfaces sem acessibilidade;
- execução multiapp por missões.

### 0.11 — Professional Packs executáveis
- Office: DOCX/XLSX/PPTX/PDF;
- Maya: Python/MEL e scene operations;
- Data/ML: datasets, notebooks e pipelines;
- Marketing/Research: browser + documentos + analytics;
- Operations: arquivos, planilhas e sistemas web.

### 0.12 — Voice-first Desktop
- nome do assistente por usuário;
- wake word configurável;
- STT pt-BR + TTS + interrupção;
- Tauri iniciar backend e voz automaticamente;
- tray, startup Windows e recovery.

### 0.13 — Accounts & commercial foundation
- cadastro/login;
- verificação SendGrid;
- esqueci minha senha;
- sessão persistente segura;
- isolamento por usuário;
- telemetria opt-in, updater e instalador.
