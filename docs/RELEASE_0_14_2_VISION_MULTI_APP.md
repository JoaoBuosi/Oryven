# Oryven 0.14.2 — Vision Provider + Multi-App Voice Missions

## 0.14.1 — Screen Understanding

- `computer.window.understand` is a separately approved action.
- The approved HWND/PID/title identity is revalidated before capture.
- Screenshots remain ephemeral and are not written to chat memory or audit payloads.
- `uia-fused` is the safe default provider: it combines the visual evidence fingerprint with bounded UI Automation metadata and does not claim pixel understanding.
- Optional local multimodal understanding can be enabled with an Ollama vision model:
  - `ORYVEN_VISION_PROVIDER=ollama`
  - `ORYVEN_VISION_MODEL=<local vision model>`
  - `ORYVEN_VISION_OLLAMA_URL=http://127.0.0.1:11434`
- Visual/page/document content is always treated as untrusted data. A scene never grants execution permission.

API:
- `POST /api/perception/window/understand/propose`

## 0.14.2 — Voice Multi-App Missions

The first deterministic multi-app template supports an Excel-to-Word workflow.
The user selects a safe mission context once:

- workspace
- exact `.xlsx` path inside that workspace
- exact `.docx` report path

API:
- `GET /api/missions/context`
- `POST /api/missions/context`
- `POST /api/missions/multi-app/plan`
- `POST /api/missions/multi-app/start`

With context configured, a voice command such as:

> Atlas, abra o Excel, analise essa planilha, crie um relatório no Word e me mostre o resultado.

becomes a three-step governed mission:

1. `office.open.document` for the exact XLSX.
2. `office.report.from.xlsx` analyzes the workbook and creates a DOCX from the measured analysis.
3. `office.open.document` for the generated DOCX.

Every step receives an independent one-shot approval and still requires mission verification before advancing. If context is missing, Oryven returns `needs_context` instead of guessing a file.

## Security invariants

- Screen understanding does not authorize clicks or typing.
- Model output is untrusted observation only.
- No arbitrary path is opened outside the configured workspace.
- Office document opening is Windows-only and limited to `.xlsx`, `.docx`, `.pptx`, and `.pdf`.
- The report is generated from workbook analysis, not from a fabricated summary.
- No mission receives blanket permission.
