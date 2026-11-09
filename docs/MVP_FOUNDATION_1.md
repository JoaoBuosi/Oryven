# Oryven MVP Foundation 1 — 0.7.0

## Delivered in this increment

- Restored local persistent chat memory endpoints.
- Added named Developer Runtime actions:
  - workspace.inspect
  - git.status / git.diff / git.push
  - test.python / test.npm / test.maven
  - build.npm / build.maven
  - deploy.vercel.preview / deploy.vercel.production
- Every developer action uses the existing one-shot approval flow.
- Developer Runtime uses argv + `shell=False`; no arbitrary command endpoint was introduced.
- Workspaces can be restricted with `ORYVEN_DEVELOPER_ROOTS`.
- Added local dependency-free Multinomial Naive Bayes intent model and training pipeline.
- Added `/api/ml/intent` for classification-only inspection.
- Added `/api/developer/propose` for explicit developer actions.
- Updated health/status version to `0.7.0-mvp-foundation1`.

## Security invariants

1. ML never grants execution permission.
2. Buno responses remain untrusted text and cannot become tool calls automatically.
3. External actions such as `git.push` and Vercel deploy still require one-shot approval.
4. Developer actions are fixed operations, not arbitrary PowerShell/cmd strings.
5. `GIT_TERMINAL_PROMPT=0` prevents hidden interactive credential prompts.

## Windows validation still required

- Actual Git authentication and remote push.
- npm/Maven availability and project-specific tests/builds.
- Vercel CLI authentication and preview/production deployment.
- Voice stack, UI Automation and Tauri on Windows.
- Buno token integration and real chat round trip.
