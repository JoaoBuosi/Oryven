# Oryven 0.11.0 — Professional Skill Packs

A 0.11 transforma parte do catálogo profissional da 0.9/0.10 em adaptadores locais executáveis e verificáveis, sempre atrás da governança one-shot do Oryven.

## Packs ativados

- `documents.compose`: cria Markdown/TXT local.
- `presentation.compose`: cria outline de apresentação em Markdown.
- `spreadsheet.analyze`: perfil de CSV (ausências, cardinalidade, estatísticas numéricas).
- `analytics.analyze`: análise descritiva de CSV e frequências.
- `datasets.prepare`: trim + remoção de linhas duplicadas, preservando o arquivo fonte.
- `design.assist`: inventário de assets de design/mídia/3D por metadados.
- `database.query`: SQLite local somente leitura (`mode=ro` + `PRAGMA query_only`).
- `knowledge.organize`: índice de metadados de arquivos textuais/código, sem copiar o conteúdo.
- `maya.assist`: prepara script Python/MEL em arquivo para revisão humana; não executa Maya automaticamente.

## Modelo de segurança

1. O agente recomenda uma skill.
2. A skill valida workspace e parâmetros antes da proposta.
3. `ApprovalStore` vincula autorização à ação e argumentos exatos.
4. A execução ocorre apenas após aprovação one-shot.
5. O runtime revalida o workspace/arquivo no momento da execução.
6. Auditoria registra tipo/estado, não o conteúdo privado completo.

## Limites deliberados

- CSV até 5 MB / 50 mil linhas no runtime local desta versão.
- `documents.compose` aceita `.md` e `.txt`.
- `presentation.compose` gera outline `.md`, não `.pptx` ainda.
- `database.query` aceita apenas SQLite local e leitura.
- `maya.assist` gera `.py`/`.mel` para revisão; execução dentro do Maya depende de validação Windows/Maya posterior.
- Office nativo, CRM, ERP e apps SaaS continuam exigindo integrações específicas ou Computer Operator.

## Critério de aceite backend

- Suíte completa: 113 testes passando.
- Nenhum pack executa sem autorização.
- Nenhum workspace pode escapar de `ORYVEN_WORK_ROOTS` quando configurado.
- Escritas preservam fonte quando a operação define saída separada.
