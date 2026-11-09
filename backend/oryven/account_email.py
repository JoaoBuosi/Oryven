"""Email delivery for Oryven verification and password-recovery codes.

Supports:
- Supabase Edge Function relay (preferred for production)
- direct SendGrid fallback
"""
from __future__ import annotations

import httpx


class EmailDeliveryError(RuntimeError):
    pass


class SendGridMailer:
    def __init__(
        self,
        api_key: str,
        from_email: str,
        from_name: str = "Oryven by Buno AI",
        hook_url: str = "",
        hook_secret: str = "",
    ):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.hook_url = (hook_url or "").strip()
        self.hook_secret = (hook_secret or "").strip()

    @property
    def hook_configured(self) -> bool:
        return bool(self.hook_url and self.hook_secret)

    @property
    def configured(self) -> bool:
        return self.hook_configured or bool(self.api_key and self.from_email)

    def _send_via_hook(self, email: str, code: str, purpose: str) -> None:
        try:
            response = httpx.post(
                self.hook_url,
                headers={
                    "x-oryven-email-secret": self.hook_secret,
                    "Content-Type": "application/json",
                },
                json={"email": email, "otp": code, "purpose": purpose},
                timeout=10.0,
            )
            if response.status_code not in {200, 202}:
                raise EmailDeliveryError(
                    f"Serviço de e-mail do Oryven recusou o envio (HTTP {response.status_code})."
                )
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Não foi possível enviar o e-mail agora.") from exc

    def _send_via_sendgrid(self, email: str, code: str, purpose: str) -> None:
        if purpose == "verify_email":
            subject = "Verifique sua conta Oryven"
            title = "Código de verificação"
        elif purpose == "reset_password":
            subject = "Recuperação de senha Oryven"
            title = "Código de recuperação"
        else:
            raise EmailDeliveryError("Finalidade de e-mail inválida.")
        payload = {
            "personalizations": [{"to": [{"email": email}], "subject": subject}],
            "from": {"email": self.from_email, "name": self.from_name},
            "content": [{
                "type": "text/plain",
                "value": f"{title}: {code}\n\nEste código expira em 10 minutos. Se você não solicitou isso, ignore esta mensagem.",
            }],
        }
        try:
            response = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10.0,
            )
            if response.status_code not in {200, 202}:
                raise EmailDeliveryError(
                    f"SendGrid recusou o envio (HTTP {response.status_code})."
                )
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Não foi possível enviar o e-mail agora.") from exc

    def send_code(self, email: str, code: str, purpose: str) -> None:
        if not self.configured:
            raise EmailDeliveryError("Envio de e-mail do Oryven ainda não está configurado.")
        if purpose not in {"verify_email", "reset_password"}:
            raise EmailDeliveryError("Finalidade de e-mail inválida.")

        if self.hook_configured:
            self._send_via_hook(email, code, purpose)
            return

        self._send_via_sendgrid(email, code, purpose)
