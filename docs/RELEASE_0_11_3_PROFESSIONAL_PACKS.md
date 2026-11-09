# Oryven 0.11.3 - Professional Packs

Esta release consolida os increments 0.11.1, 0.11.2 e 0.11.3 sobre a base 0.11.0.

## 0.11.1 - Office Pack real

Executável e governado por ApprovalStore:

- `documents.docx.compose`: cria DOCX estruturado.
- `spreadsheet.xlsx.create`: cria XLSX com múltiplas abas, cabeçalhos, freeze pane e larguras básicas.
- `spreadsheet.xlsx.analyze`: analisa estrutura de XLSX em modo de leitura.
- `presentation.pptx.compose`: cria PPTX estruturado.
- `pdf.compose`: cria PDF textual estruturado.

Dependências adicionais ficam em `requirements-professional.txt`.

## 0.11.2 - Creative & Engineering Packs

- `maya.assist`: prepara Python/MEL para revisão.
- `maya.execute`: executa script por Maya/mayapy somente após aprovação e quando o executável está explicitamente disponível/configurado.
- `blender.assist`: prepara Python para revisão.
- `blender.execute`: executa Blender em background somente após aprovação e quando instalado/configurado.
- `cad.assets.inspect`: inventário read-only de DWG/DXF/STEP/IGES.
- `bim.assets.inspect`: inventário read-only de RVT/RFA/IFC.
- `media.assets.inspect`: inventário read-only de imagens, vídeo e áudio.

Variáveis opcionais:

- `ORYVEN_MAYA_EXECUTABLE`
- `ORYVEN_BLENDER_EXECUTABLE`

Integrações profundas dentro da GUI de Maya, Blender, AutoCAD/Revit ainda dependem de validação Windows/aplicativo e não são declaradas como concluídas por esta release.

## 0.11.3 - Business Packs

- `marketing.plan`: gera plano de campanha local para revisão.
- `ecommerce.catalog.audit`: auditoria de catálogo CSV.
- `crm.pipeline.analyze`: análise de pipeline CSV.
- `operations.sop.compose`: gera SOP local.
- `logistics.analyze`: análise descritiva CSV.
- `hr.organize`: organização descritiva, sem ranking ou decisão sobre pessoas.
- `finance.workbook.analyze`: análise de XLSX sem movimentação financeira.
- `accounting.reconcile.preview`: prévia de conciliação em novo CSV, sem lançamento contábil.
- `support.triage`: análise descritiva de tickets, sem envio ou fechamento automático.

## Segurança

- Todas as ações continuam exigindo autorização one-shot.
- Workspaces são restritos pelo WorkRuntime.
- Ferramentas externas usam `subprocess` com `shell=False`.
- Maya/Blender não executam se o binário não estiver disponível/configurado.
- Skills de RH não ranqueiam nem decidem sobre pessoas.
- Skills financeiras não movimentam fundos.
- Business packs não publicam, enviam mensagens ou modificam sistemas externos automaticamente nesta release.

## Validação

- `python -m compileall backend/oryven`: OK
- suíte backend: 118 testes aprovados
- smoke API/core: 61 skills carregadas; DOCX real criado via fluxo propose -> approve -> execute

## Próximo gate

0.12 - Voice-first + Tauri Desktop: inicialização desktop independente, conta/sessão, wake word configurável, STT/TTS e UX de execução/autorizações.
