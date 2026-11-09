"""Bound, revalidated Windows UI Automation actions for the Universal Computer Operator.

Every preview captures the top-level window identity plus an exact bounded UIA path.
Execution re-resolves both identities after one-shot approval. No coordinates, global
keyboard injection, clipboard, password fields or hidden document bodies are used.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any
import time

from .computer_control import ComputerControlError, WindowInspector, _limited
from .models import (
    WindowFocusIntent, WindowButtonIntent, WindowControlInvokeIntent, WindowVisualSnapshotIntent, WindowTextInputIntent,
)


class WindowActionError(ComputerControlError):
    pass


BUTTON_TO_STATE = {
    "maximize": 1, "maximizar": 1,
    "restore": 0, "restaurar": 0,
    "minimize": 2, "minimizar": 2,
}
INVOKABLE_TYPES = frozenset({"Button", "MenuItem", "Hyperlink", "TabItem"})


class WindowActions:
    def __init__(self, inspector: WindowInspector | None = None, *, sleeper=None, clock=None):
        self.inspector = inspector or WindowInspector()
        self.sleep = sleeper or time.sleep
        self.clock = clock or time.monotonic

    @staticmethod
    def _signature(window) -> dict[str, Any]:
        info = window.element_info
        pid = getattr(info, "process_id", None)
        class_name = _limited(getattr(info, "class_name", ""), 100)
        raw_title = window.window_text()
        title = _limited(raw_title, 110)
        if not isinstance(pid, int) or pid <= 0 or not class_name or not title:
            raise WindowActionError("Janela sem identificação UIA suficiente para execução segura.")
        return {"handle": int(window.handle), "process_id": pid,
                "window_class": class_name, "window_title": title,
                "window_title_hash": sha256(str(raw_title).encode("utf-8")).hexdigest()}

    def _window(self, handle: int):
        if not isinstance(handle, int) or handle <= 0:
            raise WindowActionError("HWND inválido.")
        matches = [w for w in self.inspector._visible_windows() if w.handle == handle]
        if len(matches) != 1:
            raise WindowActionError("Janela não encontrada ou não é mais única/visível.")
        return matches[0]

    @staticmethod
    def _check_identity(window, intent):
        actual = WindowActions._signature(window)
        expected = {"handle": intent.handle, "process_id": intent.process_id,
                    "window_class": intent.window_class, "window_title": intent.window_title,
                    "window_title_hash": intent.window_title_hash}
        if actual != expected:
            raise WindowActionError("A identidade da janela mudou desde a autorização. Inspecione novamente.")

    @staticmethod
    def _control(window, path: tuple[int, ...]):
        if not 1 <= len(path) <= 4 or any(not 0 <= index < 30 for index in path):
            raise WindowActionError("Caminho do controle fora da inspeção autorizada.")
        node = window
        for index in path:
            info = node.element_info
            if getattr(info, "is_password", False) or str(getattr(info, "control_type", "")).casefold() in {"password"}:
                raise WindowActionError("Não é permitido acessar controles de senha.")
            try:
                children = node.children()[:30]
            except Exception as exc:
                raise WindowActionError("A estrutura UIA da janela mudou.") from exc
            if index >= len(children):
                raise WindowActionError("O elemento não existe mais no caminho aprovado.")
            node = children[index]
        info = node.element_info
        if getattr(info, "is_password", False) or str(getattr(info, "control_type", "")).casefold() == "password":
            raise WindowActionError("Não é permitido acessar controles de senha.")
        return node

    @staticmethod
    def _control_signature(control) -> dict[str, str]:
        info = control.element_info
        if getattr(info, "is_password", False):
            raise WindowActionError("Controle de senha não pode ser operado.")
        return {
            "control_type": _limited(getattr(info, "control_type", ""), 60),
            "control_name": _limited(getattr(info, "name", ""), 120),
            "control_automation_id": _limited(getattr(info, "automation_id", getattr(info, "auto_id", "")), 120),
        }

    @staticmethod
    def _ensure_interactable(control):
        try:
            if not control.is_visible() or not control.is_enabled():
                raise WindowActionError("O controle não está visível e habilitado.")
        except WindowActionError:
            raise
        except Exception as exc:
            raise WindowActionError("Não foi possível verificar a disponibilidade do controle.") from exc

    @staticmethod
    def _button_signature(control):
        sig = WindowActions._control_signature(control)
        if sig["control_type"] != "Button":
            raise WindowActionError("O controle aprovado deixou de ser um botão.")
        if sig["control_name"].casefold() not in BUTTON_TO_STATE:
            raise WindowActionError("Botão fora da lista legada verificável: maximizar, restaurar ou minimizar.")
        WindowActions._ensure_interactable(control)
        return {"button_name": sig["control_name"], "button_automation_id": sig["control_automation_id"]}

    def preview_focus(self, handle: int) -> WindowFocusIntent:
        window = self._window(handle)
        return WindowFocusIntent(**self._signature(window))

    def preview_button(self, handle: int, path: tuple[int, ...]) -> WindowButtonIntent:
        window = self._window(handle)
        inspected = self.inspector.inspect_window(handle)
        matches = [e for e in inspected["elements"] if tuple(e["path"]) == path]
        # Preserve the old narrowly verified button endpoint for compatibility.
        if len(matches) != 1 or matches[0]["control_type"] != "Button":
            raise WindowActionError("Controle não disponível na inspeção UIA.")
        button = self._control(window, path)
        identity = self._signature(window)
        return WindowButtonIntent(**identity, path=path, **self._button_signature(button))

    def preview_visual_snapshot(self, handle: int) -> WindowVisualSnapshotIntent:
        window = self._window(handle)
        return WindowVisualSnapshotIntent(**self._signature(window))

    def preview_invoke(self, handle: int, path: tuple[int, ...]) -> WindowControlInvokeIntent:
        window = self._window(handle)
        inspected = self.inspector.inspect_window(handle)
        matches = [e for e in inspected["elements"] if tuple(e["path"]) == path]
        if len(matches) != 1 or matches[0].get("eligible_action") != "computer.control.invoke":
            raise WindowActionError("Controle não foi exposto como invocável na inspeção atual.")
        control = self._control(window, path)
        self._ensure_interactable(control)
        sig = self._control_signature(control)
        if sig["control_type"] not in INVOKABLE_TYPES or not (sig["control_name"] or sig["control_automation_id"]):
            raise WindowActionError("Tipo de controle não permitido para InvokePattern.")
        return WindowControlInvokeIntent(**self._signature(window), path=path, **sig)

    def preview_set_text(self, handle: int, path: tuple[int, ...], text: str, replace: bool = True) -> WindowTextInputIntent:
        if not replace:
            raise WindowActionError("A 0.10 permite somente substituição explícita; anexar texto fica para uma versão posterior.")
        window = self._window(handle)
        inspected = self.inspector.inspect_window(handle)
        matches = [e for e in inspected["elements"] if tuple(e["path"]) == path]
        if len(matches) != 1 or matches[0].get("eligible_action") != "computer.control.set_text":
            raise WindowActionError("Campo não foi exposto como editável e não sensível na inspeção atual.")
        control = self._control(window, path)
        self._ensure_interactable(control)
        sig = self._control_signature(control)
        if sig["control_type"] != "Edit" or not sig["control_automation_id"]:
            raise WindowActionError("Somente campos Edit não-senha com AutomationId podem receber texto.")
        # UIA Name on Edit controls can mirror the current user content. Never carry it
        # into approvals, audit-adjacent metadata or fingerprints; AutomationId + path
        # + top-level window identity bind the target instead.
        sig["control_name"] = ""
        return WindowTextInputIntent(**self._signature(window), path=path, text=text, replace=True, **sig)

    @staticmethod
    def _assert_same_control(control, intent):
        actual = WindowActions._control_signature(control)
        if isinstance(intent, WindowTextInputIntent) and intent.control_type == "Edit":
            if (actual["control_type"] != intent.control_type or
                    actual["control_automation_id"] != intent.control_automation_id):
                raise WindowActionError("O campo mudou desde a autorização. Inspecione novamente.")
            return
        expected = {"control_type": intent.control_type, "control_name": intent.control_name,
                    "control_automation_id": intent.control_automation_id}
        if actual != expected:
            raise WindowActionError("O controle mudou desde a autorização. Inspecione novamente.")

    def execute_focus(self, intent: WindowFocusIntent) -> dict[str, Any]:
        window = self._window(intent.handle)
        self._check_identity(window, intent)
        try:
            was_active = bool(window.is_active())
            window.set_focus()
            confirmed = False
            for _ in range(5):
                if window.is_active(): confirmed = True; break
                self.sleep(0.12)
        except Exception as exc:
            raise WindowActionError("Não foi possível selecionar a janela por UI Automation.") from exc
        return {"outcome": "verified" if confirmed else "unverified", "verified": confirmed,
                "action": "computer.window.focus", "handle": intent.handle,
                "before_active": was_active, "after_active": confirmed,
                "message": "Janela em foco confirmada." if confirmed else "Foco solicitado, mas não confirmado."}

    def execute_button(self, intent: WindowButtonIntent) -> dict[str, Any]:
        window = self._window(intent.handle); self._check_identity(window, intent)
        button = self._control(window, intent.path)
        if self._button_signature(button) != {"button_name": intent.button_name, "button_automation_id": intent.button_automation_id}:
            raise WindowActionError("O botão mudou desde a autorização. Solicite nova inspeção.")
        try: original = window.get_show_state()
        except Exception as exc: raise WindowActionError("Janela não fornece WindowPattern para verificar o resultado.") from exc
        expected = BUTTON_TO_STATE[intent.button_name.casefold()]
        if original == expected: raise WindowActionError("A janela já está nesse estado. Nenhum botão foi acionado.")
        try: button.invoke()
        except Exception as exc: raise WindowActionError("O botão não aceita InvokePattern ou sua invocação falhou.") from exc
        observed = None
        try:
            for _ in range(8):
                observed = window.get_show_state()
                if observed == expected: break
                self.sleep(0.15)
        except Exception:
            return {"outcome":"unverified","verified":False,"action":"computer.button.invoke","handle":intent.handle,
                    "before_state":original,"message":"Botão invocado; o estado final não pôde ser consultado."}
        verified = observed == expected
        return {"outcome":"verified" if verified else "unverified","verified":verified,"action":"computer.button.invoke",
                "handle":intent.handle,"before_state":original,"expected_state":expected,"observed_state":observed,
                "message":"Estado final verificado por UI Automation." if verified else "Botão invocado, mas a mudança de estado não foi verificada."}

    def execute_invoke(self, intent: WindowControlInvokeIntent) -> dict[str, Any]:
        window = self._window(intent.handle); self._check_identity(window, intent)
        control = self._control(window, intent.path); self._ensure_interactable(control); self._assert_same_control(control, intent)
        if intent.control_type not in INVOKABLE_TYPES:
            raise WindowActionError("Controle não pertence aos tipos invocáveis permitidos.")
        try:
            control.invoke()
        except Exception as exc:
            raise WindowActionError("O controle não aceitou InvokePattern.") from exc
        # Generic InvokePattern often has no objective postcondition. Never retry and
        # never claim success merely because invoke() returned.
        return {"outcome":"unverified","verified":False,"action":"computer.control.invoke",
                "handle":intent.handle,"path":list(intent.path),
                "message":"Controle invocado uma vez; valide o efeito na interface antes de continuar."}

    def execute_set_text(self, intent: WindowTextInputIntent) -> dict[str, Any]:
        window = self._window(intent.handle); self._check_identity(window, intent)
        control = self._control(window, intent.path); self._ensure_interactable(control); self._assert_same_control(control, intent)
        if intent.control_type != "Edit" or not intent.control_automation_id or not intent.replace:
            raise WindowActionError("Campo não atende aos requisitos de escrita supervisionada.")
        try:
            if hasattr(control, "set_edit_text"):
                control.set_edit_text(intent.text)
            elif hasattr(control, "iface_value"):
                control.iface_value.SetValue(intent.text)
            else:
                raise WindowActionError("Campo não oferece ValuePattern/EditWrapper para escrita segura.")
        except WindowActionError:
            raise
        except Exception as exc:
            raise WindowActionError("Não foi possível definir o texto no campo aprovado.") from exc
        verified = False
        try:
            if hasattr(control, "get_value"):
                verified = control.get_value() == intent.text
            elif hasattr(control, "iface_value"):
                verified = str(control.iface_value.CurrentValue) == intent.text
        except Exception:
            verified = False
        return {"outcome":"verified" if verified else "unverified","verified":verified,
                "action":"computer.control.set_text","handle":intent.handle,"path":list(intent.path),
                "characters_written":len(intent.text),
                "message":"Texto definido e verificado." if verified else "Texto definido; o valor final não pôde ser verificado."}
