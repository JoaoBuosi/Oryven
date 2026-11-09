# Oryven 0.16.3 — Context Engine

## Objetivo
Conectar Projects, Professional Memory, Missions e Buno AI Planner sem enviar contexto excessivo ou caminhos locais absolutos para o modelo.

## Implementado
- Projeto ativo persistente por usuário em `context.json`.
- Context Engine com seleção determinística de memória por projeto, tipo e relevância lexical.
- Memória global pode complementar o projeto ativo; memórias de outros projetos não entram.
- Limite padrão de 8 memórias por bundle de contexto.
- Redaction adicional para segredos, caminhos locais e identificadores longos.
- Workspace absoluto fica apenas no contexto local.
- Buno recebe `__ORYVEN_ACTIVE_WORKSPACE__` no lugar do caminho real.
- Oryven substitui o token pelo caminho real somente depois do plano retornar e antes da validação/execução.
- Planner autônomo local recebe o workspace real do projeto ativo sem precisar de contexto explícito.
- Recovery do Buno usa o mesmo mecanismo de binding protegido.
- APIs para consultar/alterar projeto ativo e pré-visualizar o contexto minimizado.
- Product Shell mostra projeto ativo e prévia das memórias/contexto selecionados.

## APIs
- `GET /api/context`
- `PATCH /api/context/active-project`
- `POST /api/context/preview`

## Segurança
- Ativar um projeto não concede acesso ao filesystem.
- Contexto não concede permissão nem aprovação.
- Conteúdo visual, documentos e memória continuam sendo dados não confiáveis.
- Caminhos absolutos não são enviados à Buno AI pelo Context Engine.
- Memória profissional desativada resulta em zero notas de memória enviadas.
- Nenhuma memória é gravada automaticamente nesta versão.

## Validação
- Backend: 155 testes aprovados.
- TSX: transpilação sintática aprovada.
- Build Vite/Tauri/NSIS continua sendo gate Windows/local com dependências instaladas.
