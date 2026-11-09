# Validação 0.16.0

Executado no ambiente de desenvolvimento:

- `python -m compileall backend/oryven`: OK
- testes específicos do Buno AI Mission Planner: 6 passed
- regressão completa backend: 147 passed

Cobertura nova:

- plano Buno válido;
- correção de plano limitada a uma tentativa;
- rejeição de campos extras/permissões;
- bloqueio de workspace fora da allowlist;
- self-correction Buno após falha sem auto-aprovação;
- endpoints `/api/missions/ai/plan` e `/api/missions/ai/start`.

Pendente no Windows/local:

- Buno AI em `127.0.0.1:8000`;
- JWT válido em `ORYVEN_BUNO_BEARER_TOKEN`;
- planejamento real via `/api/v1/chat/stream`;
- missão real com ao menos duas skills e recovery real.
