# Oryven 0.16.4 — Evidence & Mission Intelligence

## Objetivo
Tornar o Mission Center explicável e auditável sem expor chain-of-thought ou dados sensíveis.

## Implementado
- `mission_intelligence.sqlite3` separado do store de execução.
- Metadados por missão: planner, agente, justificativa resumida, contexto minimizado e IDs de memória selecionada.
- Timeline de evidências: proposta, autorização negada, execução, falha, verificação automática/manual e recovery.
- Redaction de secrets, tokens, chaves e caminhos locais antes da persistência.
- `GET /api/missions/{mission_id}/intelligence`.
- Mission Center com painel de evidências sob demanda.
- Exclusão de missão também remove seu histórico de inteligência.
- `chain_of_thought_exposed` permanece sempre `false`.

## Limites deliberados
- Não armazena prompt bruto da Buno AI.
- Não armazena chain-of-thought.
- Não persiste screenshot bruto ou conteúdo de arquivo nesta camada.
- Evidência é resumo operacional; não substitui auditoria técnica nem autorização.
- O frontend carrega inteligência sob demanda para evitar polling pesado.

## Validação
- Suíte backend: 159 testes aprovados.
- `compileall` do backend aprovado.
- TSX validado por `transpileModule` TypeScript, sem diagnostics de sintaxe.
- Build Vite/Tauri/NSIS continua como gate Windows com dependências locais instaladas.
