# Validation — Oryven 0.14.0

- Backend compileall: PASS
- Backend test suite: 132 passed
- Visual snapshot one-shot approval: PASS (fake Windows UIA backend)
- Snapshot ephemeral flag + hash/dimensions: PASS
- Window identity revalidation: PASS
- Skill mission two-step approval/verification flow: PASS
- API `/api/perception/window/propose`: PASS
- API `/api/missions/skills`: PASS

Pending on a real Windows host:
- Pillow/ImageGrab capture of actual HWND bounds
- multi-monitor and DPI scaling
- Tauri/NSIS build gate from 0.12.1
- real microphone/wake-word flow combined with a professional mission
- multimodal Vision Provider (not part of 0.14.0 foundation)
