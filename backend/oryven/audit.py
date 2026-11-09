"""Minimal SQLite audit; does not persist transcribed speech or search queries."""
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
import sqlite3


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, action_id TEXT, kind TEXT NOT NULL, outcome TEXT NOT NULL)")

    def _connect(self):
        return sqlite3.connect(str(self.path), timeout=5)

    def write(self, kind: str, outcome: str, action_id: str | None = None):
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO events (at, action_id, kind, outcome) VALUES (?, ?, ?, ?)", (datetime.now(timezone.utc).isoformat(), action_id, kind, outcome))

    def list(self, limit: int = 50):
        with self._lock, self._connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT id, at, action_id, kind, outcome FROM events ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 200),)).fetchall()
            return [dict(row) for row in rows]

    def clear(self):
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM events")
