# Validação 0.15.0

## Ambiente atual

Validação de backend executada com:

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
```

Resultado:

```text
141 passed
```

Também validado:

```bash
python -m py_compile backend/oryven/autonomous_orchestrator.py backend/oryven/missions.py backend/oryven/core.py backend/oryven/api.py
```

## Cobertura nova

- planner detectando projeto Python;
- planner recusando adivinhar workspace;
- duas etapas com somente uma autorização pendente por vez;
- verificação automática de filesystem;
- recuperação após falha real de `terminal.run`;
- orçamento de recuperação;
- APIs `plan/start/status/advance`.

## Gates ainda dependentes do Windows

A release reaproveita os gates anteriores para Tauri, NSIS, UI Automation, voz, wake word, visão de tela e apps reais. Esses itens devem ser revalidados no Windows antes de lançamento comercial.
