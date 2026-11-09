"""User-scoped projects/workspaces for Oryven.

The store lives under the authenticated user's data_dir. Project paths are
metadata only: a project never grants filesystem permission. Runtime access is
still enforced by WorkRuntime/DeveloperRuntime allowlists and governance.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import RLock


class ProjectError(ValueError):
    pass


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    workspace: str
    description: str
    favorite_agents: tuple[str, ...]
    created_at: float
    updated_at: float

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "workspace": self.workspace,
            "description": self.description,
            "favorite_agents": list(self.favorite_agents),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProjectStore:
    def __init__(self, path: Path, now=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or time.time
        self._lock = RLock()
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    favorite_agents TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_workspace ON projects(workspace);
                """
            )

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _name(value: str) -> str:
        value = " ".join((value or "").strip().split())
        if not (2 <= len(value) <= 80):
            raise ProjectError("O nome do projeto deve ter entre 2 e 80 caracteres.")
        return value

    @staticmethod
    def _workspace(value: str) -> str:
        raw = (value or "").strip()
        if not raw or len(raw) > 1000:
            raise ProjectError("Informe um workspace válido.")
        return str(Path(raw).expanduser().resolve(strict=False))

    @staticmethod
    def _description(value: str) -> str:
        value = (value or "").strip()
        if len(value) > 1000:
            raise ProjectError("A descrição deve ter no máximo 1000 caracteres.")
        return value

    @staticmethod
    def _agents(values) -> tuple[str, ...]:
        result = []
        for value in values or []:
            item = str(value).strip()
            if item and item not in result:
                result.append(item[:120])
            if len(result) >= 12:
                break
        return tuple(result)

    @staticmethod
    def _row(row) -> Project:
        try:
            agents = tuple(json.loads(row["favorite_agents"]))
        except Exception:
            agents = ()
        return Project(str(row["id"]), str(row["name"]), str(row["workspace"]),
                       str(row["description"]), agents, float(row["created_at"]), float(row["updated_at"]))

    def create(self, name: str, workspace: str, description: str = "", favorite_agents=None) -> dict:
        project_id = str(uuid.uuid4())
        now = self._now()
        values = (project_id, self._name(name), self._workspace(workspace), self._description(description),
                  json.dumps(self._agents(favorite_agents), ensure_ascii=False), now, now)
        with self._lock, self._connect() as db:
            try:
                db.execute("INSERT INTO projects(id,name,workspace,description,favorite_agents,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", values)
            except sqlite3.IntegrityError as exc:
                raise ProjectError("Já existe um projeto para esse workspace.") from exc
        return self.get(project_id)

    def list(self) -> list[dict]:
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT * FROM projects ORDER BY updated_at DESC, name COLLATE NOCASE").fetchall()
        return [self._row(row).as_dict() for row in rows]

    def get(self, project_id: str) -> dict:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise ProjectError("Projeto não encontrado.")
        return self._row(row).as_dict()

    def update(self, project_id: str, *, name=None, description=None, favorite_agents=None) -> dict:
        current = self.get(project_id)
        next_name = self._name(name) if name is not None else current["name"]
        next_desc = self._description(description) if description is not None else current["description"]
        next_agents = self._agents(favorite_agents) if favorite_agents is not None else tuple(current["favorite_agents"])
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute("UPDATE projects SET name=?,description=?,favorite_agents=?,updated_at=? WHERE id=?",
                       (next_name, next_desc, json.dumps(next_agents, ensure_ascii=False), now, project_id))
        return self.get(project_id)

    def delete(self, project_id: str) -> dict:
        current = self.get(project_id)
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return {"deleted": True, "project": current}
