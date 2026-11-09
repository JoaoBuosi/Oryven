from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
import json
import re
import sqlite3
import uuid

_SECRET_KEY = re.compile(r"(?i)(password|senha|token|secret|api[_ -]?key|authorization|bearer|private[_ -]?key|refresh[_ -]?token)")
_WIN_PATH = re.compile(r"\b[A-Za-z]:\\[^\n\r]{1,240}")
_UNIX_HOME = re.compile(r"/(?:home|Users)/[^\s]{1,220}")
_POSIX_PATH = re.compile(r"/(?:[^\s/]+/)+[^\s,;]{1,180}")
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_text(value: str, limit: int = 900) -> str:
    text = " ".join((value or "").strip().split())[:limit]
    if _SECRET_KEY.search(text):
        return "[conteúdo sensível omitido]"
    text = _WIN_PATH.sub("[caminho local omitido]", text)
    text = _UNIX_HOME.sub("[caminho local omitido]", text)
    text = _POSIX_PATH.sub("[caminho local omitido]", text)
    text = _LONG_TOKEN.sub("[identificador longo omitido]", text)
    return text


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[profundidade omitida]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:40]:
            if _SECRET_KEY.search(str(key)):
                out[str(key)] = "[omitido]"
            else:
                out[str(key)] = sanitize(item, depth + 1)
        return out
    if isinstance(value, list):
        return [sanitize(item, depth + 1) for item in value[:30]]
    if isinstance(value, tuple):
        return [sanitize(item, depth + 1) for item in value[:30]]
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _redact_text(str(value))


class MissionIntelligenceStore:
    """Explainability records without model chain-of-thought or sensitive raw payloads."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS mission_intelligence (
                    mission_id TEXT PRIMARY KEY,
                    planner TEXT NOT NULL,
                    agent_id TEXT NOT NULL DEFAULT '',
                    reason_summary TEXT NOT NULL DEFAULT '',
                    context_json TEXT NOT NULL DEFAULT '{}',
                    memory_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_evidence (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    step_index INTEGER,
                    phase TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mission_evidence_mid ON mission_evidence(mission_id, created_at);
            """)

    def _db(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def register(self, mission_id: str, *, planner: str, agent_id: str = "", reason_summary: str = "",
                 context: dict | None = None, selected_memory_ids: list[str] | tuple[str, ...] | None = None) -> None:
        now = _now()
        payload = json.dumps(sanitize(context or {}), ensure_ascii=False)
        memory = json.dumps([str(x) for x in (selected_memory_ids or [])][:20], ensure_ascii=False)
        with self._lock, self._db() as db:
            db.execute(
                """INSERT OR REPLACE INTO mission_intelligence
                (mission_id,planner,agent_id,reason_summary,context_json,memory_ids_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,COALESCE((SELECT created_at FROM mission_intelligence WHERE mission_id=?),?),?)""",
                (mission_id, planner[:80], agent_id[:120], _redact_text(reason_summary, 600), payload, memory,
                 mission_id, now, now)
            )

    def add(self, mission_id: str, *, phase: str, outcome: str, summary: str,
            step_index: int | None = None, evidence: dict | None = None) -> None:
        now = _now()
        with self._lock, self._db() as db:
            db.execute(
                "INSERT INTO mission_evidence VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), mission_id, step_index, phase[:80], outcome[:80], _redact_text(summary, 700),
                 json.dumps(sanitize(evidence or {}), ensure_ascii=False), now)
            )
            db.execute("UPDATE mission_intelligence SET updated_at=? WHERE mission_id=?", (now, mission_id))

    def get(self, mission_id: str) -> dict:
        with self._lock, self._db() as db:
            meta = db.execute("SELECT * FROM mission_intelligence WHERE mission_id=?", (mission_id,)).fetchone()
            events = db.execute("SELECT * FROM mission_evidence WHERE mission_id=? ORDER BY created_at,id", (mission_id,)).fetchall()
        if meta is None:
            return {"mission_id": mission_id, "planner": "unknown", "agent_id": "", "reason_summary": "",
                    "context": {}, "selected_memory_ids": [], "events": [], "chain_of_thought_exposed": False}
        return {
            "mission_id": mission_id,
            "planner": meta["planner"],
            "agent_id": meta["agent_id"],
            "reason_summary": meta["reason_summary"],
            "context": json.loads(meta["context_json"] or "{}"),
            "selected_memory_ids": json.loads(meta["memory_ids_json"] or "[]"),
            "events": [{
                "id": r["id"], "step_index": r["step_index"], "phase": r["phase"], "outcome": r["outcome"],
                "summary": r["summary"], "evidence": json.loads(r["evidence_json"] or "{}"), "created_at": r["created_at"]
            } for r in events],
            "chain_of_thought_exposed": False,
        }

    def delete(self, mission_id: str) -> None:
        with self._lock, self._db() as db:
            db.execute("DELETE FROM mission_evidence WHERE mission_id=?", (mission_id,))
            db.execute("DELETE FROM mission_intelligence WHERE mission_id=?", (mission_id,))
