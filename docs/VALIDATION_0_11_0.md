# Validation report — Oryven 0.11.0

## Automatizado

- `PYTHONPATH=backend pytest -q backend/tests`: 113 passed.
- `python -m compileall backend/oryven`: deve permanecer verde no pacote final.

## Validado em testes

- documentos e outline somente após aprovação;
- CSV analytics e perfil;
- preparação de dataset preservando fonte;
- SQLite somente leitura;
- inventário de assets sem ler conteúdo;
- índice de conhecimento sem expor conteúdo;
- preparação de script Maya sem executá-lo;
- proposta/API de Professional Skill Pack;
- regressão das versões anteriores.

## Pendências Windows

- build React/Vite com dependências instaladas;
- teste Tauri;
- teste real de Maya instalado;
- validação com Office instalado;
- teste de grandes diretórios/assets em hardware alvo.
