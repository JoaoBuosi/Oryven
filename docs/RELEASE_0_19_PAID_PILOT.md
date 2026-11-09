# Oryven 0.19.0 — Paid Pilot MVP

## Goal
Turn the Functional MVP into a product that can be offered to a small, controlled paid pilot without weakening execution governance.

## Commercial capabilities
- Free/Pilot/Pro entitlement model separated from execution permissions.
- Pilot license activation using SHA-256 comparison; raw license key is not persisted.
- Versioned Terms and Privacy consent.
- Official MVP flows require accepted consent + Pilot/Pro entitlement in authenticated product mode.
- Minimal telemetry is opt-in and allowlisted.
- Feedback stored locally until a production support backend is configured.
- User-data export excludes session credentials and internal secrets.
- Password-confirmed local account deletion revokes sessions and deletes the isolated user directory.
- Safe support diagnostics explicitly report that secrets are excluded.
- Update status surface is prepared; automatic installation remains disabled until a signed production manifest is configured.

## External production gates
- Configure `ORYVEN_LICENSE_KEY_SHA256` for each paid pilot distribution/cohort.
- Choose and connect billing provider; the current build intentionally does not charge cards.
- Legal review of Terms/Privacy and executed pilot agreement.
- Production support/feedback destination.
- Signed update manifest and updater validation on Windows.
- Real SendGrid, Buno JWT, microphone/voice, Tauri/NSIS and clean-PC acceptance.
- Real pilot users and support process.
