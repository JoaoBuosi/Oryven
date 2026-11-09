# Próximos passos do MVP Oryven

## Produto-alvo

O MVP comercial será a composição de três pilares:

1. Voice-first desktop assistant.
2. Universal Computer Operator governado.
3. Professional Multi-Agent Platform extensível por skills.

## Fluxo final desejado

```text
"Atlas, prepare o relatório mensal e publique o dashboard de teste"
                         |
                         v
                  Voice Runtime
                         |
                         v
                  Buno Intelligence
                         |
                         v
               Professional Router
              /          |           \
       Data Agent   Office Agent   DevOps Agent
              \          |           /
                 Skill/Mission Plan
                         |
                  Human Approval
                         |
          +--------------+---------------+
          |              |               |
      Files/Office     Browser/UI      Terminal/Git
          |              |               |
          +--------------+---------------+
                         |
                  Verification Layer
                         |
                       Report
```

## Regra estrutural

Agentes são especializações de raciocínio e seleção de ferramentas. Skills são capacidades concretas. Runtime executa capacidades. Governance decide se a ação aprovada pode acontecer. Nenhum agente recebe acesso direto ao sistema operacional.
