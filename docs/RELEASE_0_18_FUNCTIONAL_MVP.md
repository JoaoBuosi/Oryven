# Oryven 0.18.0 — Functional MVP

Oryven 0.18.0 defines five official product journeys. A journey is not considered usable because a skill exists; it must pass through context validation, mission creation, one-shot authorization, execution, verification and result reporting.

## Official journeys

1. Development — inspect an active software workspace and run the detected test suite.
2. Office & Data — analyze XLSX and generate a real DOCX report.
3. Research & Knowledge — organize an authorized local knowledge workspace.
4. Computer Assistant — list/read authorized project files without leaving the workspace.
5. Professional Multi-App — generate a DOCX from XLSX and propose opening the exact artifact in the Windows-associated application.

The first four can be exercised without Windows UI automation. The final `office.open.document` step is a Windows visual gate and remains subject to explicit approval and human/visual verification.

## Functional MVP invariant

Planning never grants permission. Every step still enters `awaiting_approval`, and no flow can invent a workspace or file path when required context is missing.

## API

- `GET /api/mvp/flows`
- `POST /api/mvp/flows/{flow_id}/plan`
- `POST /api/mvp/flows/{flow_id}/start`

## Validation

Run:

```powershell
.\scripts\functional-mvp-smoke.ps1
```

Then complete the Windows visual gate for the Multi-App flow.
