"""One-shot, exact-target, expiring approvals; never blanket capability grants."""
from dataclasses import dataclass
from hashlib import sha256
import json
import secrets
from threading import RLock
import time
from urllib.parse import urlencode
from .models import (PendingAction, ExecutableIntent, SearchIntent, AppLaunchIntent, WindowListIntent, WindowTreeIntent,
                     BrowserInspectIntent, BunoChatIntent, WindowFocusIntent, WindowButtonIntent, DeveloperActionIntent,
                     WorkActionIntent, DynamicAppLaunchIntent, WindowControlInvokeIntent, WindowVisualSnapshotIntent, WindowUnderstandIntent, WindowTextInputIntent, ProfessionalActionIntent)


class ApprovalError(Exception):
    pass


@dataclass
class _Grant:
    pending: PendingAction
    intent: ExecutableIntent


class ApprovalStore:
    def __init__(self, ttl_seconds: int = 120, clock=None):
        self.ttl_seconds = ttl_seconds
        self.clock = clock or time.time
        self._lock = RLock()
        self._items: dict[str, _Grant] = {}

    @staticmethod
    def target_for(intent: ExecutableIntent) -> str:
        if isinstance(intent, SearchIntent):
            return "https://www.google.com/search?" + urlencode({"q": intent.query})
        if isinstance(intent, AppLaunchIntent):
            return f"windows-known-app:{intent.app_id}"
        if isinstance(intent, WindowListIntent):
            return "windows-ui-automation:visible-top-level-windows"
        if isinstance(intent, WindowTreeIntent):
            return f"windows-ui-automation:window:{intent.handle}:metadata"
        if isinstance(intent, BrowserInspectIntent):
            from .browser_control import approved_public_url
            return approved_public_url(intent.url)
        if isinstance(intent, BunoChatIntent):
            return "buno-local:chat:" + sha256(intent.message.encode("utf-8")).hexdigest()
        if isinstance(intent, WindowButtonIntent):
            return f"uia-window:{intent.handle}:pid:{intent.process_id}:button:{intent.button_name}:path:{'.'.join(str(v) for v in intent.path)}"
        if isinstance(intent, WindowControlInvokeIntent):
            return f"uia-window:{intent.handle}:pid:{intent.process_id}:invoke:{intent.control_type}:{intent.control_automation_id}:path:{'.'.join(str(v) for v in intent.path)}"
        if isinstance(intent, WindowVisualSnapshotIntent):
            return f"uia-window:{intent.handle}:pid:{intent.process_id}:visual-snapshot:{intent.window_title_hash}"
        if isinstance(intent, WindowUnderstandIntent):
            prompt_hash = sha256(intent.prompt.encode("utf-8")).hexdigest()
            return f"uia-window:{intent.handle}:pid:{intent.process_id}:screen-understanding:{intent.window_title_hash}:{prompt_hash}"
        if isinstance(intent, WindowTextInputIntent):
            text_hash = sha256(intent.text.encode("utf-8")).hexdigest()
            return f"uia-window:{intent.handle}:pid:{intent.process_id}:set-text:{intent.control_automation_id}:path:{'.'.join(str(v) for v in intent.path)}:{text_hash}"
        if isinstance(intent, WindowFocusIntent):
            return f"uia-window:{intent.handle}:pid:{intent.process_id}:focus"
        if isinstance(intent, DynamicAppLaunchIntent):
            return f"windows-discovered-app:{intent.target_type}:{sha256(intent.launch_target.encode('utf-8')).hexdigest()}"
        if isinstance(intent, DeveloperActionIntent):
            return f"developer:{intent.action}:{intent.workspace}"
        if isinstance(intent, ProfessionalActionIntent):
            args_hash = sha256(json.dumps(intent.arguments, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            return f"professional:{intent.action}:{intent.workspace}:{args_hash}"
        if isinstance(intent, WorkActionIntent):
            if intent.action == "terminal.run":
                argv_hash = sha256(json.dumps([intent.executable, *(intent.args or [])], ensure_ascii=False).encode("utf-8")).hexdigest()
                return f"work:terminal:{intent.workspace}:{argv_hash}"
            content_hash = sha256((intent.content or "").encode("utf-8")).hexdigest() if intent.content is not None else "none"
            return f"work:{intent.action}:{intent.workspace}:{intent.path}:{content_hash}"
        raise ApprovalError("Ferramenta não suportada.")

    @staticmethod
    def description_for(intent: ExecutableIntent) -> str:
        if isinstance(intent, SearchIntent):
            return f"Pesquisar no navegador por: {intent.query}"
        if isinstance(intent, AppLaunchIntent):
            return f"Abrir aplicativo permitido: {intent.app_id}"
        if isinstance(intent, WindowListIntent):
            return "Ler títulos de até 25 janelas visíveis (dados podem ser pessoais)"
        if isinstance(intent, WindowTreeIntent):
            return f"Ler até 50 metadados de controles da janela {intent.handle}"
        if isinstance(intent, BrowserInspectIntent):
            return f"Abrir página pública em navegador isolado e ler título e cabeçalhos: {intent.url}"
        if isinstance(intent, BunoChatIntent):
            return f"Enviar {len(intent.message)} caracteres à Buno AI e receber texto (a Buno pode armazenar a conversa)"
        if isinstance(intent, WindowButtonIntent):
            return (f"Invocar botão '{intent.button_name}' na janela '{intent.window_title}' "
                    f"(HWND {intent.handle}, PID {intent.process_id}); verificar estado final")
        if isinstance(intent, WindowControlInvokeIntent):
            label = intent.control_name or intent.control_automation_id or intent.control_type
            return (f"OPERAR CONTROLE: invocar {intent.control_type} '{label}' na janela '{intent.window_title}' "
                    f"(HWND {intent.handle}, PID {intent.process_id}); efeito pode exigir verificação visual")
        if isinstance(intent, WindowVisualSnapshotIntent):
            return (f"CAPTURAR JANELA: obter snapshot visual somente da janela '{intent.window_title}' "
                    f"(HWND {intent.handle}, PID {intent.process_id}); imagem não será persistida automaticamente")
        if isinstance(intent, WindowUnderstandIntent):
            return (f"ENTENDER TELA: capturar e analisar somente a janela '{intent.window_title}' "
                    f"(HWND {intent.handle}, PID {intent.process_id}); conteúdo da tela é dado não confiável e não autoriza ações")
        if isinstance(intent, WindowTextInputIntent):
            label = intent.control_name or intent.control_automation_id or "campo editável"
            return (f"DIGITAR EM CAMPO: substituir conteúdo de '{label}' na janela '{intent.window_title}' "
                    f"por {len(intent.text)} caracteres; o texto não é exibido nesta autorização")
        if isinstance(intent, WindowFocusIntent):
            return f"Selecionar a janela '{intent.window_title}' (HWND {intent.handle}, PID {intent.process_id}); verificar foco"
        if isinstance(intent, DynamicAppLaunchIntent):
            return f"ABRIR APLICATIVO DESCOBERTO: {intent.app_name} ({intent.target_type})"
        if isinstance(intent, DeveloperActionIntent):
            high = intent.action in {"git.push", "deploy.vercel.preview", "deploy.vercel.production"}
            prefix = "AÇÃO EXTERNA: " if high else ""
            return f"{prefix}{intent.action} no workspace {intent.workspace}"
        if isinstance(intent, ProfessionalActionIntent):
            write_actions = {
                "documents.compose", "documents.docx.compose", "presentation.compose",
                "presentation.pptx.compose", "spreadsheet.xlsx.create", "pdf.compose",
                "datasets.prepare", "maya.assist", "blender.assist", "marketing.plan",
                "operations.sop.compose", "accounting.reconcile.preview", "office.report.from.xlsx",
            }
            external_actions = {"maya.execute", "blender.execute", "office.open.document"}
            if intent.action in external_actions:
                return f"AÇÃO EXTERNA PROFISSIONAL: {intent.action} em {intent.workspace}; executará ferramenta instalada após aprovação"
            if intent.action in write_actions:
                return f"PROFESSIONAL SKILL: {intent.action} em {intent.workspace}; produzirá/alterará arquivo após aprovação"
            if intent.action == "database.query":
                return f"PROFESSIONAL SKILL: consulta SQLite somente leitura em {intent.workspace}"
            return f"PROFESSIONAL SKILL: {intent.action} em {intent.workspace}; leitura/análise local"
        if isinstance(intent, WorkActionIntent):
            if intent.action == "terminal.run":
                argv = " ".join([intent.executable or "", *(intent.args or [])])
                return f"TERMINAL SUPERVISIONADO: executar [{argv[:700]}] em {intent.workspace}"
            if intent.action in {"filesystem.write_text", "filesystem.append_text"}:
                return f"ALTERAR ARQUIVO: {intent.action} em {intent.workspace} / {intent.path} ({len(intent.content or '')} caracteres)"
            if intent.action == "filesystem.mkdir":
                return f"CRIAR PASTA: {intent.workspace} / {intent.path}"
            return f"{intent.action} em {intent.workspace} / {intent.path}"
        raise ApprovalError("Ferramenta não suportada.")

    @classmethod
    def fingerprint_for(cls, intent: ExecutableIntent):
        # Sign exact canonical action and arguments, not human-readable text.
        raw = json.dumps({"kind": intent.kind, "target": cls.target_for(intent),
                          "parameters": intent.model_dump()}, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return sha256(raw).hexdigest()

    def propose(self, intent: ExecutableIntent) -> PendingAction:
        pending = PendingAction(
            id=secrets.token_urlsafe(24), kind=intent.kind,
            description=self.description_for(intent), target=self.target_for(intent),
            expires_at=self.clock() + self.ttl_seconds,
            fingerprint=self.fingerprint_for(intent),
        )
        with self._lock:
            self._prune()
            self._items[pending.id] = _Grant(pending, intent)
        return pending

    def _prune(self):
        now = self.clock()
        for action_id in [key for key, val in self._items.items() if val.pending.expires_at <= now]:
            del self._items[action_id]

    def list_pending(self) -> list[PendingAction]:
        with self._lock:
            self._prune()
            return [g.pending for g in self._items.values()]

    def decide(self, action_id: str, approved: bool) -> ExecutableIntent | None:
        with self._lock:
            grant = self._items.pop(action_id, None)
            if grant is None or grant.pending.expires_at <= self.clock():
                raise ApprovalError("A aprovação não existe, já foi usada ou expirou.")
            if not approved:
                return None
            if not secrets.compare_digest(self.fingerprint_for(grant.intent), grant.pending.fingerprint):
                raise ApprovalError("O conteúdo da ação mudou; solicite nova aprovação.")
            return grant.intent

    def cancel_one(self, action_id: str) -> bool:
        """Revoke one unconsumed proposal, e.g. when a mission is cancelled."""
        with self._lock:
            return self._items.pop(action_id, None) is not None

    def cancel_all(self) -> int:
        with self._lock:
            count = len(self._items)
            self._items.clear()
            return count
