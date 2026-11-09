# Oryven 0.19.1 — Production Activation

## Estado
A release contém adapters para Stripe Checkout, webhook assinado, telemetria/feedback remotos, SendGrid real, Buno real e Tauri updater assinado.

## Segredos do serviço remoto
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_PRICE_PILOT
- STRIPE_SUCCESS_URL
- STRIPE_CANCEL_URL
- ORYVEN_PILOT_API_TOKEN

Nunca distribuir esses valores no desktop.

## Desktop
- ORYVEN_PILOT_SERVICE_URL
- ORYVEN_PILOT_SERVICE_TOKEN
- SENDGRID_API_KEY (temporariamente local enquanto auth/email continuar local-first)
- SENDGRID_FROM_EMAIL
- ORYVEN_BUNO_API_URL=http://127.0.0.1:8000
- ORYVEN_BUNO_BEARER_TOKEN
- ORYVEN_UPDATE_MANIFEST_URL

## Stripe
Checkout usa `mode=subscription`. O entitlement deve ser sincronizado a partir de webhook, não do redirect do navegador. Eventos de pagamento/webhook são a fonte confiável para fulfillment.

## Updater
Tauri exige assinatura de update. Gere a key uma única vez, mantenha a private key fora do repositório e injete apenas a public key na configuração. O build deve usar TAURI_SIGNING_PRIVATE_KEY e opcionalmente TAURI_SIGNING_PRIVATE_KEY_PASSWORD.

## GATES externos
Nenhum script consegue fabricar: credenciais Stripe/SendGrid, certificado/chave privada, JWT Buno, Windows real ou usuários reais. Esses gates devem produzir evidência antes de chamar o ambiente de produção.

## Deployment real desta sessão
O Oryven Pilot Service foi provisionado no Railway e atingiu deployment `SUCCESS`.
Base URL: `https://oryven-pilot-api-production.up.railway.app`
Webhook Stripe: `https://oryven-pilot-api-production.up.railway.app/v1/stripe/webhook`

O serviço permanece fail-closed nas rotas protegidas enquanto `ORYVEN_PILOT_API_TOKEN` não estiver definido, e checkout/webhook permanecem indisponíveis até as credenciais Stripe correspondentes serem configuradas.
