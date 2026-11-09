# Oryven 0.16.0 — Buno AI Mission Planner + Self-Correction

## Objetivo

Permitir que a Buno Intelligence proponha planos dinâmicos usando o catálogo real de agentes e skills do Oryven sem receber autoridade de execução.

## Contrato de segurança

A saída do modelo é sempre entrada não confiável. Planejamento não concede permissão.

Fluxo:

1. Oryven roteia localmente o agente profissional.
2. Oryven seleciona apenas skills executáveis do catálogo instalado.
3. Buno recebe objetivo, contexto reduzido e catálogo permitido.
4. Buno devolve JSON estrito.
5. Oryven valida schema, agent_id, skill_id, argumentos e limite de passos.
6. Oryven revalida cada intent contra o runtime real e os workspaces autorizados.
7. Só então uma Mission pode ser criada.
8. Cada etapa continua exigindo autorização one-shot.

Campos extras como `permissions_granted`, `auto_approve` ou qualquer outro campo não previsto fazem o plano ser rejeitado.

## Correção de plano

Se a primeira resposta da Buno falhar no validator, o Oryven permite exatamente uma nova tentativa de correção, enviando apenas o erro de validação. A segunda resposta é validada do zero. Não há loop ilimitado.

## Self-correction após falha

Quando uma etapa falha e existe orçamento de recuperação:

- a Buno pode sugerir exatamente uma etapa diagnóstica;
- a sugestão precisa usar skill permitida e argumentos válidos;
- o Oryven revalida a etapa no runtime local;
- a etapa entra em `awaiting_approval`;
- a ação original só é tentada novamente depois da recuperação e com nova autorização.

Se a Buno estiver indisponível ou a recuperação for inválida, a política local da 0.15 continua disponível como fallback.

## Privacidade

O contexto enviado ao planner é allowlisted. Chaves arbitrárias não são encaminhadas. O recovery não envia conteúdo de arquivos, texto digitado, mensagens ou argumentos de terminal; envia apenas metadados mínimos necessários para diagnóstico.

## APIs

- `POST /api/missions/ai/plan`
- `POST /api/missions/ai/start`
- APIs autônomas da 0.15 permanecem disponíveis.

## Configuração necessária

`ORYVEN_BUNO_BEARER_TOKEN` deve conter um JWT válido da Buno AI. O token não deve ser armazenado no frontend, logs ou repositório.

## Limites conhecidos

- A validação real com a Buno local depende de token/servidor ativos no Windows do usuário.
- A Buno não pode inventar skills fora do catálogo ou trocar o agente roteado localmente.
- Máximo de 8 etapas por missão.
- O planner não possui poder de auto-aprovação.
