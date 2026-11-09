from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

import httpx


class RemoteServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemoteServicesConfig:
    base_url: str = ""
    api_token: str = ""
    timeout_seconds: float = 12.0

    @property
    def configured(self) -> bool:
        return bool(self.base_url.strip())


class PilotServiceClient:
    """HTTPS client for billing, telemetry and feedback.

    The desktop never receives Stripe secret keys. It talks only to the
    remotely deployed Oryven Pilot Service.
    """

    def __init__(self, config: RemoteServicesConfig):
        self.config = config

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_token:
            headers["Authorization"] = f"Bearer {self.config.api_token}"
        return headers

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.config.configured:
            raise RemoteServiceError("Serviço comercial remoto não configurado.")
        url = self.config.base_url.rstrip("/") + path
        try:
            response = httpx.post(url, headers=self._headers(), json=payload, timeout=self.config.timeout_seconds)
            if response.status_code >= 400:
                raise RemoteServiceError(f"Serviço remoto recusou a operação (HTTP {response.status_code}).")
            return response.json()
        except httpx.HTTPError as exc:
            raise RemoteServiceError("Serviço comercial remoto indisponível.") from exc

    def create_checkout(self, *, user_id: str, email: str, plan: str = "pilot") -> dict[str, Any]:
        return self._post("/v1/billing/checkout", {"user_id": user_id, "email": email, "plan": plan})

    def entitlement(self, *, user_id: str) -> dict[str, Any]:
        if not self.config.configured:
            raise RemoteServiceError("Serviço comercial remoto não configurado.")
        url = self.config.base_url.rstrip("/") + "/v1/billing/entitlement"
        try:
            response = httpx.get(url, headers=self._headers(), params={"user_id": user_id}, timeout=self.config.timeout_seconds)
            if response.status_code >= 400:
                raise RemoteServiceError(f"Serviço remoto recusou a operação (HTTP {response.status_code}).")
            return response.json()
        except httpx.HTTPError as exc:
            raise RemoteServiceError("Serviço comercial remoto indisponível.") from exc

    def telemetry(self, event: str, properties: dict[str, Any]) -> bool:
        self._post("/v1/telemetry", {"event": event, "properties": properties})
        return True

    def feedback(self, *, user_id: str, category: str, message: str, diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._post("/v1/feedback", {
            "user_id": user_id,
            "category": category,
            "message": message,
            "diagnostics": diagnostics or {},
        })
