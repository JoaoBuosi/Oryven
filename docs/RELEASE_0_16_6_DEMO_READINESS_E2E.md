# Oryven 0.16.6 — Demo Readiness + End-to-End UX

## Objective
Turn the existing product shell into a guided commercial demo flow instead of exposing technical modules without a clear next action.

## Commercial journey
Login → onboarding → active project → task by text/voice → mission → one-shot authorization → execution → verification → result/evidence.

## Added
- `/api/demo/readiness` with deterministic readiness checks and a single next action.
- Home Demo Readiness journey reflecting actual account/project/mission state.
- Mission creation guard requiring an active project for the commercial flow.
- Friendly error presentation for Buno connectivity, missing project context, approvals, voice, unsupported mission text, and local core connectivity.
- Completed mission result callout.
- `scripts/demo-smoke.ps1` and backend release tests.

## Security unchanged
Readiness never grants permissions. `permissions_granted` remains false. One-shot approvals, revalidation, user isolation, emergency stop and secret redaction remain mandatory.

## Windows gate
The complete Vite + Tauri + NSIS build still requires the Windows development environment and must be validated there before calling the installer production-ready.
