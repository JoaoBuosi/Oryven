"""Explicit, user-scoped professional memory.

Memory is opt-in and never inferred from secrets. The store keeps small facts,
preferences, decisions and project notes; callers must explicitly request a
write. Project deletion can cascade at the application layer through clear().
"""
from __future__ import annotations

import re
import sqlite3
import time
import uuid
from pathlib import Path
from threading import RLock


class ProfessionalMemoryError(ValueError):
    pass


_ALLOWED_KINDS = {"fact", "preference", "decision", "project_note"}
_SECRET_RE = re.compile(r"(?i)(password|senha|api[_ -]?key|token|bearer|secret|private[_ -]?key|refresh[_ -]?token)")


class ProfessionalMemory:
    def __init__(self, path: Path, now=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or time.time
        self._lock = RLock()
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS memory_settings (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    enabled INTEGER NOT NULL DEFAULT 1
                );
                INSERT OR IGNORE INTO memory_settings(id,enabled) VALUES (1,1);
                CREATE TABLE IF NOT EXISTS professional_memories (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'explicit',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_profmem_project ON professional_memories(project_id, updated_at DESC);
                """
            )

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def enabled(self) -> bool:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT enabled FROM memory_settings WHERE id=1").fetchone()
        return bool(row["enabled"])

    def set_enabled(self, enabled: bool) -> dict:
        with self._lock, self._connect() as db:
            db.execute("UPDATE memory_settings SET enabled=? WHERE id=1", (1 if enabled else 0,))
        return {"enabled": bool(enabled)}

    @staticmethod
    def _content(value: str) -> str:
        value = " ".join((value or "").strip().split())
        if not (2 <= len(value) <= 1200):
            raise ProfessionalMemoryError("A memória deve ter entre 2 e 1200 caracteres.")
        if _SECRET_RE.search(value):
            raise ProfessionalMemoryError("Não armazene senhas, tokens ou segredos na memória profissional.")
        return value

    def remember(self, content: str, kind: str = "fact", project_id: str | None = None) -> dict:
        if not self.enabled():
            raise ProfessionalMemoryError("A memória profissional está desativada.")
        if kind not in _ALLOWED_KINDS:
            raise ProfessionalMemoryError("Tipo de memória inválido.")
        item_id = str(uuid.uuid4())
        now = self._now()
        value = self._content(content)
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO professional_memories(id,project_id,kind,content,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                       (item_id, project_id or None, kind, value, "explicit", now, now))
        return self.get(item_id)

    def get(self, item_id: str) -> dict:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM professional_memories WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise ProfessionalMemoryError("Memória não encontrada.")
        return dict(row)

    def list(self, project_id: str | None = None, limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._lock, self._connect() as db:
            if project_id:
                rows = db.execute("SELECT * FROM professional_memories WHERE project_id=? ORDER BY updated_at DESC LIMIT ?", (project_id, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM professional_memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def delete(self, item_id: str) -> dict:
        current = self.get(item_id)
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM professional_memories WHERE id=?", (item_id,))
        return {"deleted": True, "memory": current}

    def clear(self, project_id: str | None = None) -> dict:
        with self._lock, self._connect() as db:
            if project_id:
                cur = db.execute("DELETE FROM professional_memories WHERE project_id=?", (project_id,))
            else:
                cur = db.execute("DELETE FROM professional_memories")
        return {"deleted": int(cur.rowcount), "project_id": project_id}
