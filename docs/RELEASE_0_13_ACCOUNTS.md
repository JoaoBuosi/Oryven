# Oryven 0.13 — Accounts, persistent session and user isolation

## Implemented

- Registration with full name, e-mail and password.
- PBKDF2-SHA256 password hashing with per-password random salt.
- Six-digit e-mail verification codes; only protected hashes are stored.
- SendGrid delivery via `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` and optional `SENDGRID_FROM_NAME`.
- Login with generic invalid-credential errors and in-memory access tokens.
- Persistent device session with opaque refresh token; only its SHA-256 is stored in SQLite.
- Windows persistent token protection via DPAPI. The React UI never receives the refresh token.
- Logout revokes the current persistent session.
- Forgot-password response does not disclose whether an account exists.
- Password reset uses a six-digit code and revokes all previous persistent sessions and access tokens.
- User-scoped Oryven data directories: `data/users/<user-id>/` for chat memory, voice profile, missions and audit.
- Login/register/verify/forgot/reset gateway in the React frontend.

## Required SendGrid environment

Do not commit these values:

```text
SENDGRID_API_KEY=...
SENDGRID_FROM_EMAIL=verified-sender@example.com
SENDGRID_FROM_NAME=Oryven by Buno AI
```

## Security model

The loopback `X-Oryven-Session` token remains a local desktop boundary. In production mode, protected APIs additionally require an account `Authorization: Bearer <access-token>` header. The account access token is kept only in frontend memory. On application restart `/api/auth/restore` uses the DPAPI-protected device token to create a fresh access token.

Buno AI's internal bearer token remains separate from Oryven account authentication.
