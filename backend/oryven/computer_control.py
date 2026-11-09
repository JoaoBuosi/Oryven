"""Consent-gated, read-only Windows UI Automation inventory.

Do not read edit fields, document bodies, secret values, clipboard or screenshots.
Data is returned only to the requesting UI, never stored in the audit log.
"""
from __future__ import annotations
from collections import deque
from typing import Any
import sys


class ComputerControlError(ValueError):
    pass


def _limited(value: object, length: int = 100) -> str:
    return " ".join(str(value or "").split())[:length]


class WindowInspector:
    """Uses pywinauto UIA; accepts an injectable Desktop factory for tests."""
    def __init__(self, *, platform: str | None = None, desktop_factory=None):
        self.platform = platform or sys.platform
        self.desktop_factory = desktop_factory

    def _desktop(self):
        if self.platform != "win32":
            raise ComputerControlError("A inspeção UIA exige Windows 10/11.")
        if self.desktop_factory is not None:
            return self.desktop_factory(backend="uia")
        try:
            from pywinauto import Desktop  # optional: requirements-control.txt
        except ImportError as exc:
            raise ComputerControlError("Instale requirements-control.txt para ativar Windows UIA.") from exc
        try:
            return Desktop(backend="uia")
        except Exception as exc:
            raise ComputerControlError("Não foi possível acessar Windows UI Automation.") from exc

    def _visible_windows(self):
        try:
            windows = self._desktop().windows()
        except ComputerControlError:
            raise
        except Exception as exc:
            raise ComputerControlError("Windows UI Automation não respondeu.") from exc
        found = []
        for window in windows:
            try:
                if window.is_visible() and isinstance(window.handle, int) and window.handle > 0:
                    found.append(window)
            except Exception:
                continue
        return found

    def list_windows(self) -> dict[str, Any]:
        result = []
        for w in self._visible_windows()[:25]:
            try:
                result.append({
                    "handle": int(w.handle),
                    "title": _limited(w.window_text(), 110) or "(sem título)",
                    "control_type": _limited(w.element_info.control_type, 50),
                })
            except Exception:
                continue
        return {"windows": result, "limit": 25, "complete": False,
                "privacy": "Somente títulos de janelas; podem conter dados pessoais. Não são salvos pelo Oryven."}

    def inspect_window(self, handle: int) -> dict[str, Any]:
        """Return a bounded UIA map without reading editable/document values.

        Paths for invokable controls and non-password Edit controls may be exposed so
        a later, separately approved action can target that exact element.
        """
        if not isinstance(handle, int) or handle <= 0:
            raise ComputerControlError("Identificador de janela inválido.")
        top = next((w for w in self._visible_windows() if w.handle == handle), None)
        if top is None:
            raise ComputerControlError("A janela não está mais visível ou não pertence ao desktop atual.")
        nodes = []
        queue = deque([(top, 0, ())])
        invokable_types = {"Button", "MenuItem", "Hyperlink", "TabItem"}
        blocked_invoke_names = {
            "delete", "excluir", "remove", "remover", "confirm", "confirmar",
            "send", "enviar", "ok", "submit", "purchase", "comprar",
            "pay", "pagar", "publish", "publicar",
        }
        while queue and len(nodes) < 80:
            control, depth, path = queue.popleft()
            try:
                info = control.element_info
                control_type = _limited(getattr(info, "control_type", ""), 45)
                is_password = bool(getattr(info, "is_password", False)) or control_type.casefold() == "password"
                editable_or_document = control_type.casefold() in {"edit", "document"}
                hidden_value_surface = is_password or editable_or_document
                raw_name = _limited(getattr(info, "name", ""), 120)
                name = "[omitido: conteúdo editável]" if hidden_value_surface else raw_name
                automation_id = "" if is_password else _limited(
                    getattr(info, "automation_id", getattr(info, "auto_id", "")), 100
                )
                eligible_action = None
                if not is_password:
                    if (control_type == "Button" and raw_name.casefold() in
                            {"maximize", "maximizar", "minimize", "minimizar", "restore", "restaurar"}):
                        eligible_action = "computer.button.invoke"
                    elif (control_type in invokable_types and (raw_name or automation_id)
                            and raw_name.casefold() not in blocked_invoke_names):
                        eligible_action = "computer.control.invoke"
                    elif control_type == "Edit" and automation_id:
                        eligible_action = "computer.control.set_text"
                nodes.append({
                    "depth": depth,
                    "control_type": control_type or "Unknown",
                    "name": name,
                    "automation_id": automation_id,
                    "sensitive": is_password,
                    "content_redacted": hidden_value_surface,
                    "path": list(path),
                    "eligible_action": eligible_action,
                })
                # Never descend into passwords, Edit or Document bodies. Keep the
                # traversal bounded so a malicious/huge UI tree cannot exhaust us.
                if depth < 4 and not hidden_value_surface:
                    children = control.children()
                    queue.extend((child, depth + 1, path + (i,)) for i, child in enumerate(children[:30]))
            except Exception:
                continue
        return {"handle": handle, "elements": nodes, "limit": 80, "complete": False,
                "privacy": "Metadados UIA limitados; valores de Edit/Document e senhas não são lidos. Ações exigem nova autorização."}
