# Oryven 0.15.0 — Supervised Autonomous Mission Orchestrator

## Objetivo

Fechar o loop de missão supervisionada:

1. receber objetivo;
2. selecionar agente profissional;
3. montar plano tipado com skills executáveis;
4. solicitar autorização one-shot para a próxima etapa;
5. executar somente após aprovação;
6. verificar automaticamente quando houver evidência local confiável;
7. preparar recuperação diagnóstica quando uma etapa falhar;
8. tentar novamente a etapa original somente após nova autorização;
9. interromper em revisão humana quando não houver recuperação segura ou o orçamento acabar.

Autonomia nesta release significa autonomia de planejamento, verificação e recuperação — nunca autonomia de permissão.

## Novos componentes

- `backend/oryven/autonomous_orchestrator.py`
  - `AdaptiveMissionPlanner`
  - `MissionAutonomyStore`
  - `SupervisedMissionPolicy`
- Extensões do `MissionStore` para verificação automática e injeção de recuperação.
- APIs de missão autônoma supervisionada.

## Planner adaptativo local

Templates iniciais:

- Software/DevOps: `workspace.inspect` → `git.status` → teste Python/npm/Maven detectado pelo workspace.
- Marketing: `marketing.plan`.
- Dados/IA: `analytics.analyze`.
- Finanças: `finance.workbook.analyze`.
- Office: `office.report.from.xlsx`.
- Demais áreas: `knowledge.organize` como fallback não destrutivo.

Se faltarem `workspace`, `path` ou `output`, o planner retorna `needs_context` e não adivinha valores.

Também é possível fornecer um plano tipado explícito de até oito skills. Cada skill é validada antes da criação da missão.

## Verificação automática

A verificação automática só ocorre quando existe evidência local adequada, por exemplo:

- arquivo/pasta realmente existe após criação/gravação;
- runtime analítico terminou sem erro;
- testes/builds locais terminaram sem erro;
- artefato profissional esperado foi produzido.

Ações externas como `git.push`, deploy e controle visual de aplicativos continuam exigindo confirmação humana/externa.

## Recuperação

Quando uma etapa de workspace falha, o Oryven pode inserir uma etapa diagnóstica de baixo risco (`filesystem.list`) e depois reapresentar a etapa original. Ambas continuam exigindo autorizações one-shot novas.

O orçamento de recuperação é configurável entre 0 e 2. Ao esgotar o orçamento, a missão para em `needs_review`.

## APIs

- `POST /api/missions/autonomous/plan`
- `POST /api/missions/autonomous/start`
- `GET /api/missions/{mission_id}/autonomous`
- `POST /api/missions/{mission_id}/autonomous/advance`

## Limites desta release

- O planner é determinístico e first-party; ainda não permite que um LLM gere livremente intents arbitrárias.
- Percepção visual pode informar decisões, mas não concede permissões.
- Automação entre aplicativos que depende de estado visual continua exigindo confirmação humana quando não houver evidência automática suficiente.
- Recovery não tenta “consertar” comandos externos de forma irrestrita; ele começa por diagnóstico local e seguro.
