"""Local, bounded Oryven conversation history. No automatic outbound transmission."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock


class ChatMemory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute('PRAGMA busy_timeout=5000')
        return db

    def append_exchange(self, user_text: str, answer: str):
        if not user_text.strip() or not answer.strip():
            return
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, self._connect() as db:
            db.execute('INSERT INTO messages(role, content, created_at) VALUES (?,?,?)', ('user', user_text[:500], now))
            db.execute('INSERT INTO messages(role, content, created_at) VALUES (?,?,?)', ('assistant', answer[:6000], now))
            db.execute('DELETE FROM messages WHERE id NOT IN (SELECT id FROM messages ORDER BY id DESC LIMIT 200)')

    def list_messages(self):
        with self.lock, self._connect() as db:
            rows = db.execute('SELECT id, role, content FROM messages ORDER BY id ASC').fetchall()
        return [{'id': row[0], 'role': row[1], 'text': row[2], 'status': 'done'} for row in rows]

    def clear(self):
        with self.lock, self._connect() as db:
            db.execute('DELETE FROM messages')
        return {'status': 'cleared'}
