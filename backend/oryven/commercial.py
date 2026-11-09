"""Commercial layer for Oryven Paid Pilot.

Keeps commercial entitlement/consent/telemetry separate from execution permissions.
No entitlement grants filesystem, terminal, desktop or external-action permission.
"""
from __future__ import annotations

import json
import sqlite3
import hashlib
import hmac
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

COMMERCIAL_TERMS_VERSION = "pilot-2026-11"
PRIVACY_VERSION = "pilot-2026-11"

class CommercialError(ValueError):
    pass

@dataclass(frozen=True)
class Entitlement:
    plan: str
    status: str
    source: str
    expires_at: float | None

    def as_dict(self):
        return {"plan": self.plan, "status": self.status, "source": self.source, "expires_at": self.expires_at,
                "grants_execution_permissions": False}

class CommercialStore:
    def __init__(self, path: Path, now=None):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or time.time; self._lock = RLock()
        with self._connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS entitlement(
              singleton INTEGER PRIMARY KEY CHECK(singleton=1), plan TEXT NOT NULL, status TEXT NOT NULL,
              source TEXT NOT NULL, expires_at REAL, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS consents(
              kind TEXT PRIMARY KEY, version TEXT NOT NULL, accepted INTEGER NOT NULL, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(
              key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS telemetry(
              id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, properties TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS feedback(
              id TEXT PRIMARY KEY, category TEXT NOT NULL, message TEXT NOT NULL, include_diagnostics INTEGER NOT NULL,
              created_at REAL NOT NULL);
            """)
            db.execute("INSERT OR IGNORE INTO entitlement(singleton,plan,status,source,updated_at) VALUES(1,'free','active','default',?)", (self._now(),))
            db.execute("INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES('telemetry_enabled','false',?)", (self._now(),))
    def _connect(self):
        db=sqlite3.connect(self.path, timeout=5); db.row_factory=sqlite3.Row; db.execute('PRAGMA busy_timeout=5000'); return db
    def entitlement(self):
        with self._lock,self._connect() as db: row=db.execute('SELECT * FROM entitlement WHERE singleton=1').fetchone()
        return Entitlement(str(row['plan']),str(row['status']),str(row['source']),float(row['expires_at']) if row['expires_at'] is not None else None)
    def activate_license(self, license_key: str, expected_sha256: str, expires_at: float|None=None):
        if not expected_sha256 or len(expected_sha256) != 64:
            raise CommercialError('Licenciamento de piloto não configurado nesta build.')
        digest=hashlib.sha256((license_key or '').strip().encode('utf-8')).hexdigest()
        if not hmac.compare_digest(digest.lower(), expected_sha256.lower()):
            raise CommercialError('Licença inválida.')
        return self.set_entitlement('pilot','active','pilot-license',expires_at)

    def set_entitlement(self, plan: str, status: str='active', source: str='admin', expires_at: float|None=None):
        if plan not in {'free','pilot','pro'} or status not in {'active','inactive','expired'}: raise CommercialError('Entitlement inválido.')
        with self._lock,self._connect() as db:
            db.execute('UPDATE entitlement SET plan=?,status=?,source=?,expires_at=?,updated_at=? WHERE singleton=1',(plan,status,source,expires_at,self._now()))
        return self.entitlement()
    def accept(self, kind: str, version: str, accepted: bool=True):
        if kind not in {'terms','privacy'}: raise CommercialError('Consentimento inválido.')
        expected=COMMERCIAL_TERMS_VERSION if kind=='terms' else PRIVACY_VERSION
        if version != expected: raise CommercialError('Versão de documento inválida.')
        with self._lock,self._connect() as db:
            db.execute('INSERT INTO consents(kind,version,accepted,updated_at) VALUES(?,?,?,?) ON CONFLICT(kind) DO UPDATE SET version=excluded.version,accepted=excluded.accepted,updated_at=excluded.updated_at',(kind,version,1 if accepted else 0,self._now()))
        return self.consents()
    def consents(self):
        with self._lock,self._connect() as db: rows=db.execute('SELECT kind,version,accepted,updated_at FROM consents').fetchall()
        values={r['kind']:{'version':r['version'],'accepted':bool(r['accepted']),'updated_at':r['updated_at']} for r in rows}
        return {'terms':values.get('terms',{'version':COMMERCIAL_TERMS_VERSION,'accepted':False}), 'privacy':values.get('privacy',{'version':PRIVACY_VERSION,'accepted':False})}
    def set_telemetry(self, enabled: bool):
        with self._lock,self._connect() as db:
            db.execute("INSERT INTO settings(key,value,updated_at) VALUES('telemetry_enabled',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",('true' if enabled else 'false',self._now()))
        return enabled
    def telemetry_enabled(self):
        with self._lock,self._connect() as db: row=db.execute("SELECT value FROM settings WHERE key='telemetry_enabled'").fetchone()
        return bool(row and row['value']=='true')
    def record_event(self, event: str, properties: dict|None=None):
        if not self.telemetry_enabled(): return False
        safe={k:v for k,v in (properties or {}).items() if k in {'flow','status','duration_bucket','error_class','version','surface'}}
        with self._lock,self._connect() as db: db.execute('INSERT INTO telemetry(event,properties,created_at) VALUES(?,?,?)',(event[:80],json.dumps(safe,ensure_ascii=False),self._now()))
        return True

    def telemetry_batch(self, limit: int = 100):
        with self._lock, self._connect() as db:
            rows = db.execute('SELECT id,event,properties,created_at FROM telemetry ORDER BY id LIMIT ?', (max(1,min(limit,500)),)).fetchall()
        return [{"id": int(r["id"]), "event": r["event"], "properties": json.loads(r["properties"] or "{}"), "created_at": r["created_at"]} for r in rows]

    def delete_telemetry_ids(self, ids):
        clean=[int(v) for v in ids if isinstance(v,(int,float)) or str(v).isdigit()]
        if not clean: return 0
        marks=','.join('?' for _ in clean)
        with self._lock,self._connect() as db:
            cur=db.execute(f'DELETE FROM telemetry WHERE id IN ({marks})', clean)
            return cur.rowcount

    def feedback(self, category: str, message: str, include_diagnostics: bool=False):
        msg=' '.join((message or '').strip().split())
        if not (3 <= len(msg) <= 2000): raise CommercialError('Feedback deve ter entre 3 e 2000 caracteres.')
        if category not in {'bug','idea','experience','support'}: raise CommercialError('Categoria de feedback inválida.')
        fid=str(uuid.uuid4())
        with self._lock,self._connect() as db: db.execute('INSERT INTO feedback(id,category,message,include_diagnostics,created_at) VALUES(?,?,?,?,?)',(fid,category,msg,1 if include_diagnostics else 0,self._now()))
        return {'id':fid,'category':category,'include_diagnostics':include_diagnostics,'stored_locally':True}

class DataPortability:
    SAFE_NAMES={'projects.sqlite3','professional_memory.sqlite3','onboarding.json','context.json','voice_profile.json','missions.sqlite3','mission_intelligence.sqlite3','chat_memory.sqlite3','commercial.sqlite3'}
    @classmethod
    def export_user_data(cls, data_dir: Path, output: Path):
        data_dir=Path(data_dir); output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
        manifest={'format':'oryven-user-export-v1','generated_at':time.time(),'files':[]}
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
            for name in sorted(cls.SAFE_NAMES):
                p=data_dir/name
                if p.exists() and p.is_file(): z.write(p,arcname=name); manifest['files'].append(name)
            z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        return {'path':str(output),'files':manifest['files'],'contains_credentials':False}
