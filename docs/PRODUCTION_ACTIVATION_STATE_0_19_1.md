# Oryven 0.19.1 — Production Activation State

## Remote Pilot Service

Railway project: `oryven-pilot-service`

- Project ID: `b0f6420d-006d-4b8c-83df-764f30e5c87d`
- Environment: `production`
- Environment ID: `1e0d9307-4ab7-450e-8ce1-a477365421d8`
- Service: `oryven-pilot-api`
- Service ID: `bf635773-1533-4c6a-8976-26f4a574529d`
- Persistent volume: `oryven-pilot-data` (500 MB)
- Public base URL: `https://oryven-pilot-api-production.up.railway.app`
- Stripe webhook URL: `https://oryven-pilot-api-production.up.railway.app/v1/stripe/webhook`
- Health path: `/health`

Railway deployment reached `SUCCESS` with one running replica and no reported issues.

## Remote API contract

- `GET /health`
- `POST /v1/billing/checkout`
- `GET /v1/billing/entitlement?user_id=...`
- `POST /v1/stripe/webhook`
- `POST /v1/telemetry`
- `POST /v1/feedback`

The desktop now supports:

- `POST /api/commercial/billing/checkout`
- `POST /api/commercial/billing/sync`
- `POST /api/commercial/telemetry/sync`
- remote feedback delivery with local fallback

A successful Checkout redirect does not grant entitlement. The desktop only promotes the local commercial entitlement after the remote service reports a webhook-backed active Stripe entitlement.

## Secrets still required on Railway

Configure these only on the Railway service, never in the desktop bundle:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_PILOT`
- `ORYVEN_PILOT_API_TOKEN`

Already configured non-secret values:

- `ORYVEN_PILOT_DB=/data/oryven-pilot.sqlite3`
- `STRIPE_SUCCESS_URL=https://buno.ai/oryven/success`
- `STRIPE_CANCEL_URL=https://buno.ai/oryven/cancel`

## Desktop production settings

- `ORYVEN_PILOT_SERVICE_URL=https://oryven-pilot-api-production.up.railway.app`
- `ORYVEN_PILOT_SERVICE_TOKEN=<same pilot API token configured remotely>`
- `SENDGRID_API_KEY=<SendGrid API key>`
- `SENDGRID_FROM_EMAIL=<verified sender>`
- `ORYVEN_BUNO_API_URL=http://127.0.0.1:8000`
- `ORYVEN_BUNO_BEARER_TOKEN=<valid Buno JWT>`
- `ORYVEN_UPDATE_MANIFEST_URL=<signed update manifest>`

## Hard gates

These cannot be truthfully marked complete without external evidence:

1. Stripe secret/price/webhook credentials and a successful test payment.
2. SendGrid API key + verified sender + successful delivery.
3. Buno local API running + valid JWT + successful authenticated planner request.
4. Tauri/NSIS build and installer validation on Windows.
5. Tauri updater signing key + signed artifact + successful update test.
6. Legal counsel approval of Terms and LGPD/privacy documents.
7. Real pilot users completing the acceptance protocol.
