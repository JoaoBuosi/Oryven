# Oryven 0.16.2 — Onboarding + Projects + Professional Memory

## Objetivo
Transformar a Product Shell 0.16.1 em uma experiência persistente orientada ao usuário: primeira configuração, projetos/workspaces e memória profissional explícita.

## Onboarding
Estado persistido por usuário em `onboarding.json` com quatro gates:
- nome do assistente;
- voz/microfone;
- primeiro projeto/workspace;
- revisão de governança.

O onboarding não concede permissões. O gate de workspace indica apenas que o usuário cadastrou um projeto.

## Projects
`projects.sqlite3`, isolado pelo `data_dir` autenticado do usuário.

Projeto contém:
- nome;
- workspace;
- descrição;
- agentes favoritos (metadata preparada para UI futura).

Cadastrar um workspace em Projects **não** altera `ORYVEN_WORK_ROOTS` nem `ORYVEN_DEVELOPER_ROOTS` e não concede filesystem access.

## Professional Memory
`professional_memory.sqlite3`, também isolado por usuário.

Tipos suportados:
- `fact`;
- `preference`;
- `decision`;
- `project_note`.

Características:
- escrita somente explícita via API/UI;
- memória global ou vinculada a um projeto;
- toggle para desativar novas gravações;
- apagar item individual;
- apagar memória de projeto;
- exclusão de projeto remove sua memória associada;
- rejeição básica de textos que indiquem senha/token/API key/secret.

Esta memória ainda não é injetada automaticamente em prompts da Buno AI. A próxima integração deve selecionar apenas memórias necessárias ao objetivo e manter minimização de contexto.

## APIs novas
- `GET /api/onboarding`
- `PATCH /api/onboarding`
- `GET /api/projects`
- `POST /api/projects`
- `PATCH /api/projects/{id}`
- `DELETE /api/projects/{id}`
- `GET /api/memory/professional`
- `POST /api/memory/professional`
- `PATCH /api/memory/professional/settings`
- `DELETE /api/memory/professional/{id}`
- `DELETE /api/memory/professional?project_id=...`

## UI
Product Shell adiciona:
- Projects na navegação;
- Memory na navegação;
- onboarding contextual após autenticação;
- criação/exclusão de projetos;
- criação/exclusão de memórias;
- filtro por projeto;
- toggle da memória.

## Validação
- `PYTHONPATH=backend python -m pytest backend/tests -q`: **151 passed**
- `python -m compileall backend/oryven`: **pass**
- transpile sintático de `web/src/App.tsx` com TypeScript: **0 errors**

O `vite build` e o build Tauri/NSIS continuam como gates no Windows com dependências Node/Rust instaladas.
