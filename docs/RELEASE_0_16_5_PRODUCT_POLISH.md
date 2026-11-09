# Oryven 0.16.5 — Interface Polish + Mission UX + Authorization UX

## Objective
This release deliberately avoids expanding backend scope. It consolidates the existing 0.16.4 capabilities into a clearer commercial product experience.

## Changes
- Home now exposes a single operational status strip and contextual next action.
- Home metrics prioritize missions, approvals, active project, and voice state.
- Authorization Center emphasizes target, impact, scope, expiration, one-shot behavior, and fingerprint binding.
- Risk presentation is derived locally for UX only; backend governance remains authoritative.
- Projects show a dedicated active-context banner.
- Voice settings gain a first-class status panel with microphone/wake state.
- Mission cards receive stronger progress/status affordances and retain Mission Intelligence evidence.
- Product label updated to 0.16.5 Product Polish.

## Security
No approval semantics were weakened. UI risk labels are explanatory only and never authorize, deny, or change policy.

## Validation gates
- Backend regression suite must remain green.
- Python compileall must pass.
- App.tsx must transpile without syntax errors.
- Full Vite/Tauri/NSIS build remains a Windows/local dependency gate.
