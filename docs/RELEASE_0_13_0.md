# Oryven 0.13.0 — Accounts + persistent sessions + user isolation

This release includes the 0.12.1 Windows release-gate work and the 0.13 account system.

### Account flow

`register -> verify-email -> authenticated workspace -> persistent device restore -> logout`

Recovery uses `forgot-password -> six-digit code -> reset-password -> revoke previous sessions`.

### Isolation

The account database and device-session vault live under the base Oryven data directory. Each user gets a separate runtime data root at `users/<uuid>/`, so chat history, voice profile, missions and audit do not share the same SQLite/JSON files.

### Persistent session

The frontend never stores the persistent refresh credential. On Windows, `device_session.bin` is DPAPI-protected for the current Windows user. The backend stores only a SHA-256 token hash in `accounts.sqlite3`. React receives only a short-lived access token in memory.

### E-mail

SendGrid is required for real registration/recovery delivery. Configure `SENDGRID_API_KEY` and a verified `SENDGRID_FROM_EMAIL` only on the backend environment.

### Windows installer gate

Use `scripts/validate-windows-0121.ps1`; after success, `scripts/build-release-windows.ps1` creates `release/Oryven-Setup-0.13.0.exe` and its SHA-256 file.
