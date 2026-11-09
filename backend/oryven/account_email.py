"""SendGrid delivery for Oryven verification and password-recovery codes."""
from __future__ import annotations

import httpx


class EmailDeliveryError(RuntimeError):
    pass


class SendGridMailer:
    def __init__(self, api_key: str, from_email: str, from_name: str = "Oryven by Buno AI"):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.from_email)

    def send_code(self, email: str, code: str, purpose: str) -> None:
        if not self.configured:
            raise EmailDeliveryError("Envio de e-mail do Oryven ainda não está configurado.")
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
            "content": [{"type": "text/plain", "value": f"{title}: {code}\n\nEste código expira em 10 minutos. Se você não solicitou isso, ignore esta mensagem."}],
        }
        try:
            response = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=10.0,
            )
            if response.status_code not in {200, 202}:
                raise EmailDeliveryError(f"SendGrid recusou o envio (HTTP {response.status_code}).")
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Não foi possível enviar o e-mail agora.") from exc
