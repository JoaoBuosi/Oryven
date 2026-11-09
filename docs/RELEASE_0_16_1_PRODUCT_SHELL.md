# Oryven 0.16.1 — Product Shell Consolidation

## Objetivo

Esta versão inicia a fase de productization do MVP sem alterar o motor 0.16.
O foco foi substituir a tela técnica monolítica por uma navegação coerente de produto,
reutilizando somente APIs existentes.

## Auditoria resumida

### Confirmado no projeto
- Backend 0.16 com auth, voice, agents, skills, missions, computer operator, vision,
  professional runtimes e Buno AI mission planner.
- Tauri 2 e scripts de build Windows presentes.
- Frontend anterior concentrado quase inteiro em `web/src/App.tsx` e `style.css`.
- Frontend ainda exibia rótulos de MVP 0.13 apesar do backend 0.16.
- Não havia navegação de produto entre Missions, Authorizations, Agents, Skills,
  Computer e Settings.

### Mantido sem regressão
- Nenhuma mudança no backend de execução.
- Deny-by-default e one-shot approvals preservados.
- Access token continua somente em memória no frontend.
- Emergency stop continua exposto na UI.
- Planner profissional não concede permissões.

## Product Shell 0.16.1

A interface agora possui:

- Home / Command Center
- Mission Center
- Authorization Center
- Professional Agents
- Skill Library
- Computer
- Settings

### Command Center
- Orb visual ligado a estados reais do runtime: idle, listening, thinking,
  executing e awaiting approval.
- Compositor de missão unificado.
- Métricas de missões, aprovações, agentes e skills.
- Missão ativa e autorizações pendentes em destaque.
- Timeline de atividade recente.

### Mission Center
- Lista de missões com progresso.
- Estado de cada etapa.
- Verificação humana quando exigida.
- Cancelamento explícito.

### Authorization Center
- Tipo, descrição, alvo e fingerprint da ação.
- Aprovação one-shot e negação separadas.

### Agents
- Catálogo visual dos agentes reais retornados por `/api/agents`.
- Busca.
- Professional router integrado ao `/api/agents/plan`.

### Skills
- Catálogo retornado por `/api/skills`.
- Diferenciação visual READY / PLANNED.
- Família, risco e identificador.

### Computer
- Inventário de apps.
- Solicitação governada de abertura de apps.
- Entrada para inspeção Windows UIA.
- Estado visual de Vision, terminal e Core.

### Settings
- Nome do assistente.
- Wake word.
- Background listening.
- Speak on startup.
- Health da Buno AI.
- Emergency stop.

## Validação

Backend:

`PYTHONPATH=backend python -m pytest -q`

Resultado: **147 passed**.

Frontend TSX:
- Validado com `typescript.transpileModule` do TypeScript global.
- Resultado: **0 diagnostics de sintaxe/transpilação**.

Frontend Vite:
- `npm install` não concluiu dentro do limite do ambiente atual.
- Portanto `npm run build` continua sendo gate obrigatório no Windows/local.

Tauri:
- `cargo` não está disponível neste ambiente.
- Build Tauri/NSIS continua sendo gate Windows.

## Próximas prioridades

1. Onboarding de primeira execução ligado à conta.
2. Projects / Workspaces como entidade de produto.
3. Persistent Professional Memory com controles de usuário.
4. UI de evidências de Vision e execução.
5. Integração real Buno 0.16 com token válido local.
6. Build React + Tauri + NSIS em Windows.
7. Testes end-to-end em máquina limpa.
