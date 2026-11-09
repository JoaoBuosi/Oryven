from __future__ import annotations

import json, re, unicodedata
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

WORKSPACE_TOKEN = "__ORYVEN_ACTIVE_WORKSPACE__"

_SECRETISH = re.compile(r"(?i)(password|senha|api[_ -]?key|bearer|secret|private[_ -]?key|refresh[_ -]?token)")
_WIN_PATH = re.compile(r"\b[A-Za-z]:\\[^\n\r]{1,240}")
_UNIX_HOME = re.compile(r"/(?:home|Users)/[^\s]{1,220}")
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")
_WORD = re.compile(r"[A-Za-zÀ-ÿ0-9_\-]{3,}")


def _fold(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))


def _terms(text: str) -> set[str]:
    stop = {"para","com","uma","uns","das","dos","que","the","and","por","projeto","project","este","essa","isso","mais","como"}
    return {w for w in _WORD.findall(_fold(text)) if w not in stop}


def redact(text: str, limit: int = 500) -> str:
    value = " ".join((text or "").strip().split())[:limit]
    if _SECRETISH.search(value):
        return "[conteúdo sensível omitido]"
    value = _WIN_PATH.sub("[caminho local omitido]", value)
    value = _UNIX_HOME.sub("[caminho local omitido]", value)
    value = _LONG_TOKEN.sub("[identificador longo omitido]", value)
    return value


@dataclass(frozen=True)
class ContextBundle:
    public_context: dict[str, Any]
    local_context: dict[str, Any]
    bindings: dict[str, str]
    selected_memory_ids: tuple[str, ...]

    def preview(self) -> dict:
        return {
            "public_context": self.public_context,
            "local_context": {k: ("[workspace local protegido]" if k == "workspace" else v) for k, v in self.local_context.items()},
            "selected_memory_ids": list(self.selected_memory_ids),
            "bindings": list(self.bindings.keys()),
            "permissions_granted": False,
        }


class ContextEngine:
    def __init__(self, path: Path, projects, memory):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.projects = projects
        self.memory = memory
        self._lock = RLock()
        if not self.path.exists():
            self._write({"active_project_id": None})

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"active_project_id": None}

    def _write(self, payload: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def active_project(self) -> dict | None:
        pid = self._read().get("active_project_id")
        if not pid:
            return None
        try:
            return self.projects.get(str(pid))
        except Exception:
            self._write({"active_project_id": None})
            return None

    def set_active_project(self, project_id: str | None) -> dict:
        if project_id is not None:
            project = self.projects.get(project_id)
        else:
            project = None
        with self._lock:
            self._write({"active_project_id": project_id})
        return {"active_project": project, "permissions_granted": False}

    def clear_if_active(self, project_id: str) -> None:
        current = self._read().get("active_project_id")
        if current == project_id:
            self._write({"active_project_id": None})

    def _rank_memories(self, objective: str, project_id: str | None, limit: int = 8) -> list[dict]:
        if not self.memory.enabled():
            return []
        objective_terms = _terms(objective)
        items = self.memory.list(None, 500)
        ranked = []
        for item in items:
            pid = item.get("project_id")
            if pid not in (None, project_id):
                continue
            content = str(item.get("content") or "")
            if _SECRETISH.search(content):
                continue
            overlap = len(objective_terms & _terms(content))
            score = overlap * 5
            score += 4 if pid == project_id and project_id else 1
            score += {"decision": 3, "preference": 2, "project_note": 2, "fact": 1}.get(str(item.get("kind")), 0)
            ranked.append((score, float(item.get("updated_at") or 0), item))
        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [r[2] for r in ranked[:max(1, min(limit, 12))] if r[0] > 0]

    def build(self, objective: str, explicit_context: dict | None = None, memory_limit: int = 8) -> ContextBundle:
        explicit = dict(explicit_context or {})
        project = self.active_project()
        project_id = project["id"] if project else None
        selected = self._rank_memories(objective, project_id, memory_limit)
        notes = [f"{m['kind']}: {redact(str(m['content']), 360)}" for m in selected]

        public: dict[str, Any] = {}
        local: dict[str, Any] = {}
        bindings: dict[str, str] = {}
        if project:
            public.update({
                "active_project_id": project["id"],
                "project_name": redact(project["name"], 120),
                "project_description": redact(project.get("description", ""), 420),
                "workspace": WORKSPACE_TOKEN,
            })
            local["workspace"] = project["workspace"]
            bindings[WORKSPACE_TOKEN] = project["workspace"]
        if notes:
            public["memory_notes"] = notes

        # Explicit context is allowed, but absolute workspace stays local and is represented by a binding.
        for key, value in explicit.items():
            if key == "workspace" and isinstance(value, str) and value.strip():
                local["workspace"] = value
                bindings[WORKSPACE_TOKEN] = value
                public["workspace"] = WORKSPACE_TOKEN
            elif key in {"path","spreadsheet_path","report_path","output","title","audience","channels","app_name","language","format","objective_hint"}:
                if isinstance(value, str):
                    public[key] = redact(value, 700)
                    local[key] = value
                elif isinstance(value, (int,float,bool)) or value is None:
                    public[key] = value; local[key] = value
                elif isinstance(value, list):
                    public[key] = [redact(str(v), 180) for v in value[:20]]
                    local[key] = value[:20]
        return ContextBundle(public, local, bindings, tuple(str(m["id"]) for m in selected))
