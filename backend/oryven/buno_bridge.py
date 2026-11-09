"""Opt-in loopback Buno adapter. Health and separately approved text chat only."""
from __future__ import annotations
import httpx
from urllib.parse import urlsplit


class BunoConnectionError(ValueError):
    pass


class BunoHealthBridge:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", transport=None, bearer_token: str = ""):
        parsed = urlsplit(base_url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise BunoConnectionError("Porta Buno inválida.") from exc
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
                or port is None or not (1024 <= port <= 65535) or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise BunoConnectionError("Buno deve usar um endereço loopback HTTP com porta explícita.")
        self.base_url = f"http://127.0.0.1:{port}"
        self.transport = transport
        self._bearer_token = bearer_token

    def check(self) -> dict:
        try:
            with httpx.Client(timeout=2.5, follow_redirects=False, trust_env=False,
                              transport=self.transport) as client:
                response = client.get(self.base_url + "/api/v1/health")
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Malformed response")
                return {"reachable": data.get("api") == "ok", "url": self.base_url,
                        "bridge_mode": "health-only", "model_execution_enabled": False}
        except (httpx.HTTPError, ValueError) as exc:
            return {"reachable": False, "url": self.base_url,
                    "bridge_mode": "health-only", "model_execution_enabled": False,
                    "message": "Buno API indisponível ou contrato de health não reconhecido."}

    def chat(self, message: str) -> dict:
        """Calls Buno's existing authenticated SSE /api/v1/chat/stream endpoint.

        Buno may persist user messages and memories. Caller must explicitly approve
        the exact message. Output is untrusted *text*, never an executable tool call.
        """
        if not self._bearer_token:
            raise BunoConnectionError("Configure ORYVEN_BUNO_BEARER_TOKEN para usar o chat Buno.")
        if not isinstance(message, str) or not message.strip() or len(message) > 500:
            raise BunoConnectionError("Informe uma pergunta entre 1 e 500 caracteres.")
        answer = ""
        event = ""
        completed = False
        try:
            with httpx.Client(timeout=httpx.Timeout(35, connect=3), follow_redirects=False,
                              trust_env=False, transport=self.transport) as client:
                with client.stream(
                    "POST", self.base_url + "/api/v1/chat/stream",
                    json={"message": message},
                    headers={"Authorization": f"Bearer {self._bearer_token}", "Accept": "text/event-stream"},
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if len(line) > 8000:
                            raise BunoConnectionError("Evento Buno excedeu o limite de tamanho.")
                        if line.startswith("event: "):
                            event = line[7:].strip()
                        elif line.startswith("data: "):
                            import json
                            try:
                                payload = json.loads(line[6:])
                            except ValueError as exc:
                                raise BunoConnectionError("O stream Buno retornou JSON inválido.") from exc
                            if event == "chunk":
                                text = payload.get("text", "")
                                if not isinstance(text, str):
                                    raise BunoConnectionError("O stream Buno retornou texto inválido.")
                                answer += text
                                if len(answer) > 6000:
                                    raise BunoConnectionError("A resposta Buno excedeu o limite de 6.000 caracteres.")
                            elif event == "error":
                                raise BunoConnectionError("A API Buno informou falha de geração.")
                            elif event == "done":
                                completed = payload.get("status") != "error"
                                break
                        elif not line:
                            event = ""
        except (httpx.HTTPError, UnicodeError) as exc:
            raise BunoConnectionError("Não foi possível autenticar ou concluir o chat Buno.") from exc
        if not completed or not answer.strip():
            raise BunoConnectionError("A API Buno não confirmou uma resposta completa.")
        return {"answer": answer, "source": "buno-local-sse", "executed_tools": False,
                "disclosure": "Mensagem enviada à Buno; ela pode ser armazenada na conversa e memória da Buno."}

    def plan_json(self, prompt: str) -> str:
        """Ask Buno for planning JSON only. Output is untrusted and never executed directly."""
        if not self._bearer_token:
            raise BunoConnectionError("Configure ORYVEN_BUNO_BEARER_TOKEN para usar o planejador Buno.")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
            raise BunoConnectionError("Prompt do planejador Buno inválido ou grande demais.")
        answer = ""
        event = ""
        completed = False
        try:
            with httpx.Client(timeout=httpx.Timeout(60, connect=3), follow_redirects=False,
                              trust_env=False, transport=self.transport) as client:
                with client.stream(
                    "POST", self.base_url + "/api/v1/chat/stream",
                    json={"message": prompt},
                    headers={"Authorization": f"Bearer {self._bearer_token}", "Accept": "text/event-stream"},
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if len(line) > 16000:
                            raise BunoConnectionError("Evento do planejador Buno excedeu o limite.")
                        if line.startswith("event: "):
                            event = line[7:].strip()
                        elif line.startswith("data: "):
                            import json
                            try:
                                payload = json.loads(line[6:])
                            except ValueError as exc:
                                raise BunoConnectionError("Planejador Buno retornou JSON SSE inválido.") from exc
                            if event == "chunk":
                                text = payload.get("text", "")
                                if not isinstance(text, str):
                                    raise BunoConnectionError("Planejador Buno retornou chunk inválido.")
                                answer += text
                                if len(answer) > 12000:
                                    raise BunoConnectionError("Resposta do planejador Buno excedeu o limite.")
                            elif event == "error":
                                raise BunoConnectionError("A API Buno informou falha de planejamento.")
                            elif event == "done":
                                completed = payload.get("status") != "error"
                                break
                        elif not line:
                            event = ""
        except (httpx.HTTPError, UnicodeError) as exc:
            raise BunoConnectionError("Não foi possível autenticar ou concluir o planejamento Buno.") from exc
        if not completed or not answer.strip():
            raise BunoConnectionError("A API Buno não confirmou um plano completo.")
        return answer
