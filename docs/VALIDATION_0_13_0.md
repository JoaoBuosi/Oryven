# Validation report — Oryven 0.13.0

## Executed in the development container

- `PYTHONPATH=backend python -m pytest backend/tests -q` → **128 passed**.
- `PYTHONPATH=backend python -m compileall -q backend/oryven` → passed.
- Account API smoke → register, verify e-mail, protected status, `auth/me`, logout and failed restore after revocation → passed.
- User isolation regression → voice profile persisted for user A and remained default for user B → passed.
- Password recovery regression → reset invalidated old access and persistent device session → passed.

## Not validated in this container

- React/Vite production build: `npm install` did not finish within the available execution window.
- Rust/Tauri compilation: Windows Rust toolchain is not available here.
- PyInstaller Windows `.exe`, NSIS installer, Windows DPAPI, microphone/Vosk/SAPI and tray lifecycle require Windows 10/11.

Run `scripts/validate-windows-0121.ps1` on Windows. Do not mark the installer release as validated until that gate succeeds and the installer is exercised on a clean Windows profile.
