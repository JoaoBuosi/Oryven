"""Persistent, user-verified, allowlisted missions for Oryven 0.3.

Each plan is deterministic. An action requires a one-shot external approval;
dispatch never means that a real-world UI operation is verified.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
import json
import re
import sqlite3
import uuid

from .governance import ApprovalStore
from .intent import parse_intent
from pydantic import TypeAdapter
from .models import ExecutableIntent

_INTENT_ADAPTER = TypeAdapter(ExecutableIntent)


class MissionError(ValueError):
    pass


# Not an LLM planner: split only explicitly supported sequential conjunctions.
_SEPARATOR = re.compile(r"\s+(?:e\s+depois|depois|em\s+seguida|e\s+(?=(?:abra|abrir|inicie|iniciar|pesquise|pesquisar)\b))\s+", re.I)


def split_steps(text: str) -> list[str]:
    # "Abra o navegador e pesquise ..." is ONE allowed browser.search action,
    # not an unsupported attempt to launch an arbitrary browser program.
    text = re.sub(r"^\s*(?:abra|abrir)\s+o\s+navegador\s+e\s+pesquis(?:e|ar)\b",
                  "pesquise", text, count=1, flags=re.I)
    return _SEPARATOR.split(text.strip())


def plan_text(text: str) -> list[ExecutableIntent]:
    if not (1 <= len(text.strip()) <= 500):
        raise MissionError("A missão deve ter entre 1 e 500 caracteres.")
    raw_steps = split_steps(text)
    if not 1 <= len(raw_steps) <= 3:
        raise MissionError("O MVP aceita no máximo três ações conhecidas por missão.")
    intents: list[ExecutableIntent] = []
    for raw in raw_steps:
        intent = parse_intent(raw)
        if intent is None:
            raise MissionError("Missão não criada: existe uma etapa desconhecida ou não autorizada.")
        intents.append(intent)
    return intents


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionStore:
    """SQLite stores plans, state and consent verification, not audio or secrets."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self._db() as conn:
            conn.executescript("""
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_steps (
                    mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL, intent_json TEXT NOT NULL,
                    status TEXT NOT NULL, action_id TEXT, result TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (mission_id, ordinal)
                );
                CREATE INDEX IF NOT EXISTS idx_mission_actions ON mission_steps(action_id);
            """)
            # A process crash may have happened after external side effects.
            # NEVER replay uncertain dispatched commands without human review.
            conn.execute("UPDATE mission_steps SET status='needs_review', action_id=NULL WHERE status='executing'")
            conn.execute("UPDATE missions SET status='needs_review', updated_at=? WHERE status='executing'", (_now(),))
            # An in-memory approval is invalid on restart and must be reissued.
            conn.execute("UPDATE mission_steps SET status='paused', action_id=NULL WHERE status='awaiting_approval'")
            conn.execute("UPDATE missions SET status='paused', updated_at=? WHERE status='awaiting_approval'", (_now(),))

    def _db(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    def create(self, title: str, intents: list[ExecutableIntent]) -> dict:
        if not 1 <= len(intents) <= 8:
            raise MissionError("Plano fora do limite de segurança.")
        ident = str(uuid.uuid4())
        now = _now()
        with self._lock, self._db() as db:
            db.execute("INSERT INTO missions VALUES (?, ?, 'planned', ?, ?)", (ident, title, now, now))
            db.executemany("INSERT INTO mission_steps(mission_id,ordinal,intent_json,status) VALUES (?,?,?,'planned')",
                           [(ident, index, intent.model_dump_json()) for index, intent in enumerate(intents)])
        return self.get(ident)

    def _get(self, db, ident: str):
        mission = db.execute("SELECT * FROM missions WHERE id=?", (ident,)).fetchone()
        if mission is None:
            raise MissionError("Missão não encontrada.")
        steps = db.execute("SELECT * FROM mission_steps WHERE mission_id=? ORDER BY ordinal", (ident,)).fetchall()
        return mission, steps

    def _view(self, mission, steps):
        result = dict(mission)
        result["steps"] = []
        for s in steps:
            raw = json.loads(s["intent_json"])
            intent = _INTENT_ADAPTER.validate_python(raw)
            result["steps"].append({"index": s["ordinal"], "kind": intent.kind,
                "description": ApprovalStore.description_for(intent), "target": ApprovalStore.target_for(intent),
                "status": s["status"], "result": s["result"], "action_id": s["action_id"]})
        result["verification"] = "manual"  # Explicitly not automated UI verification.
        return result

    def get(self, ident: str) -> dict:
        with self._lock, self._db() as db:
            mission, steps = self._get(db, ident)
            return self._view(mission, steps)

    def list(self, limit: int = 20) -> list[dict]:
        with self._lock, self._db() as db:
            ids = [r['id'] for r in db.execute('SELECT id FROM missions ORDER BY created_at DESC LIMIT ?', (max(1, min(limit, 50)),))]
            return [self._view(*self._get(db, ident)) for ident in ids]

    def next_intent(self, ident: str) -> tuple[int, ExecutableIntent]:
        with self._lock, self._db() as db:
            mission, steps = self._get(db, ident)
            if mission['status'] not in ('planned', 'paused'):
                raise MissionError("Missão não está pronta para solicitar a próxima ação.")
            s = next((s for s in steps if s['status'] in ('planned', 'paused')), None)
            if s is None:
                raise MissionError("Esta missão não tem próxima ação disponível.")
            data = json.loads(s['intent_json'])
            try:
                intent = _INTENT_ADAPTER.validate_python(data)
            except Exception as exc:
                raise MissionError('Tipo de ação não suportado.') from exc
            return s['ordinal'], intent

    def proposed(self, ident: str, index: int, action_id: str):
        with self._lock, self._db() as db:
            row, _ = self._get(db, ident)
            if row['status'] not in ('planned', 'paused'):
                raise MissionError('Missão não pode receber aprovação neste estado.')
            update = db.execute("UPDATE mission_steps SET status='awaiting_approval', action_id=? WHERE mission_id=? AND ordinal=? AND status IN ('planned','paused')", (action_id, ident, index))
            if update.rowcount != 1:
                raise MissionError('Etapa já iniciada ou indisponível.')
            db.execute("UPDATE missions SET status='awaiting_approval', updated_at=? WHERE id=?", (_now(), ident))

    def action_owner(self, action_id: str) -> str | None:
        with self._lock, self._db() as db:
            row = db.execute("SELECT mission_id FROM mission_steps WHERE action_id=? AND status='awaiting_approval'", (action_id,)).fetchone()
            return row['mission_id'] if row else None

    def executing(self, ident: str, action_id: str):
        with self._lock, self._db() as db:
            update = db.execute("UPDATE mission_steps SET status='executing' WHERE mission_id=? AND action_id=? AND status='awaiting_approval'", (ident, action_id))
            if update.rowcount != 1:
                raise MissionError('A etapa não está aguardando essa autorização.')
            db.execute("UPDATE missions SET status='executing', updated_at=? WHERE id=?", (_now(), ident))

    def resolved(self, ident: str, action_id: str, outcome: str, message: str):
        if outcome not in ('dispatched', 'failed', 'denied'):
            raise MissionError('Resultado inesperado.')
        step_status = {'dispatched': 'awaiting_verification', 'failed': 'failed', 'denied': 'cancelled'}[outcome]
        with self._lock, self._db() as db:
            update = db.execute("UPDATE mission_steps SET status=?, result=?, action_id=NULL WHERE mission_id=? AND action_id=? AND status IN ('executing','awaiting_approval')", (step_status, message[:500], ident, action_id))
            if update.rowcount != 1:
                raise MissionError('Resultado não corresponde à ação autorizada.')
            db.execute('UPDATE missions SET status=?, updated_at=? WHERE id=?', (step_status, _now(), ident))

    def verify(self, ident: str, confirmed: bool) -> dict:
        with self._lock, self._db() as db:
            mission, steps = self._get(db, ident)
            if mission['status'] != 'awaiting_verification':
                raise MissionError('Não há ação aguardando confirmação do usuário.')
            step = next((s for s in steps if s['status']=='awaiting_verification'), None)
            if step is None:
                raise MissionError('Etapa a confirmar não encontrada.')
            db.execute("UPDATE mission_steps SET status=? WHERE mission_id=? AND ordinal=?", ('verified_by_user' if confirmed else 'failed', ident, step['ordinal']))
            next_status = 'planned' if confirmed and any(s['ordinal'] > step['ordinal'] for s in steps) else ('completed' if confirmed else 'failed')
            db.execute('UPDATE missions SET status=?, updated_at=? WHERE id=?', (next_status, _now(), ident))
        return self.get(ident)

    def step_intent(self, ident: str, *, status: str | None = None, ordinal: int | None = None) -> ExecutableIntent:
        with self._lock, self._db() as db:
            mission, steps = self._get(db, ident)
            selected = None
            if ordinal is not None:
                selected = next((s for s in steps if s['ordinal'] == ordinal), None)
            elif status is not None:
                selected = next((s for s in reversed(steps) if s['status'] == status), None)
            if selected is None:
                raise MissionError('Etapa da missão não encontrada.')
            return _INTENT_ADAPTER.validate_python(json.loads(selected['intent_json']))

    def verify_automatic(self, ident: str, confirmed: bool, note: str) -> dict:
        with self._lock, self._db() as db:
            mission, steps = self._get(db, ident)
            if mission['status'] != 'awaiting_verification':
                raise MissionError('Não há ação aguardando verificação automática.')
            step = next((s for s in steps if s['status'] == 'awaiting_verification'), None)
            if step is None:
                raise MissionError('Etapa a verificar não encontrada.')
            db.execute(
                "UPDATE mission_steps SET status=?, result=? WHERE mission_id=? AND ordinal=?",
                ('verified_automatically' if confirmed else 'failed', note[:500], ident, step['ordinal'])
            )
            next_status = 'planned' if confirmed and any(s['ordinal'] > step['ordinal'] for s in steps) else ('completed' if confirmed else 'failed')
            db.execute('UPDATE missions SET status=?, updated_at=? WHERE id=?', (next_status, _now(), ident))
        return self.get(ident)

    def inject_recovery(self, ident: str, recovery_intent: ExecutableIntent, *, retry_failed: bool = True) -> dict:
        """Insert a diagnostic step and optionally retry the exact failed intent.

        Recovery does not approve anything. New steps return to planned state and must
        receive fresh one-shot approvals.
        """
        with self._lock, self._db() as db:
            mission, steps = self._get(db, ident)
            if mission['status'] != 'failed':
                raise MissionError('Recuperação só pode ser injetada após uma etapa falhar.')
            failed = next((s for s in reversed(steps) if s['status'] == 'failed'), None)
            if failed is None:
                raise MissionError('Etapa com falha não encontrada.')
            failed_intent_json = failed['intent_json']
            insert_count = 2 if retry_failed else 1
            later = [s for s in steps if s['ordinal'] > failed['ordinal']]
            for row in sorted(later, key=lambda item: item['ordinal'], reverse=True):
                db.execute('UPDATE mission_steps SET ordinal=? WHERE mission_id=? AND ordinal=?',
                           (row['ordinal'] + insert_count, ident, row['ordinal']))
            db.execute("UPDATE mission_steps SET status='failed_recovered' WHERE mission_id=? AND ordinal=?",
                       (ident, failed['ordinal']))
            base = failed['ordinal'] + 1
            db.execute("INSERT INTO mission_steps(mission_id,ordinal,intent_json,status) VALUES (?,?,?,'planned')",
                       (ident, base, recovery_intent.model_dump_json()))
            if retry_failed:
                db.execute("INSERT INTO mission_steps(mission_id,ordinal,intent_json,status) VALUES (?,?,?,'planned')",
                           (ident, base + 1, failed_intent_json))
            db.execute("UPDATE missions SET status='planned', updated_at=? WHERE id=?", (_now(), ident))
        return self.get(ident)

    def pause(self, ident: str) -> dict:
        with self._lock, self._db() as db:
            mission, steps = self._get(db, ident)
            if mission['status'] not in ('planned', 'awaiting_approval', 'paused'):
                raise MissionError('Só é possível pausar uma missão antes da execução.')
            db.execute("UPDATE mission_steps SET status='paused', action_id=NULL WHERE mission_id=? AND status='awaiting_approval'", (ident,))
            db.execute("UPDATE missions SET status='paused', updated_at=? WHERE id=?", (_now(), ident))
        return self.get(ident)

    def pause_all_pending(self):
        with self._lock, self._db() as db:
            db.execute("UPDATE mission_steps SET status='paused', action_id=NULL WHERE status='awaiting_approval'")
            db.execute("UPDATE missions SET status='paused', updated_at=? WHERE status='awaiting_approval'", (_now(),))

    def delete(self, ident: str):
        """Allow privacy deletion of terminal records; never detach a live approval."""
        with self._lock, self._db() as db:
            mission, _ = self._get(db, ident)
            if mission['status'] not in ('completed', 'cancelled', 'failed', 'needs_review'):
                raise MissionError('Cancele ou conclua a missão antes de excluir seu histórico.')
            db.execute('DELETE FROM missions WHERE id=?', (ident,))
        return {"status": "deleted"}

    def cancel(self, ident: str):
        with self._lock, self._db() as db:
            mission, steps = self._get(db, ident)
            if mission['status'] in ('completed', 'cancelled', 'failed', 'executing', 'needs_review'):
                raise MissionError('Missão não pode ser cancelada neste estado; efeitos já iniciados não são revertidos.')
            db.execute("UPDATE mission_steps SET status=CASE WHEN status='awaiting_verification' THEN 'unverified' ELSE 'cancelled' END, action_id=NULL WHERE mission_id=? AND status IN ('planned','paused','awaiting_approval','awaiting_verification')", (ident,))
            db.execute("UPDATE missions SET status='cancelled', updated_at=? WHERE id=?", (_now(), ident))
        return self.get(ident)
