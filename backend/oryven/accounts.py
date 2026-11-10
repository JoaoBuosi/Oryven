"""Local account store for Oryven desktop.

Passwords and one-time codes are never stored in plaintext. Persistent device
sessions use opaque refresh tokens whose hashes live in SQLite; the token itself
is protected by DeviceSessionVault (DPAPI on Windows).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import string
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

PASSWORD_ITERATIONS = 600_000
CODE_ITERATIONS = 180_000


class AccountError(ValueError):
    pass


def _derive(value: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, iterations).hex()


def _hash_password(password: str) -> str:
    if not (8 <= len(password) <= 72) or len(password.encode("utf-8")) > 72:
        raise AccountError("A senha deve ter entre 8 e 72 caracteres e no máximo 72 bytes.")
    salt = secrets.token_bytes(16)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${_derive(password, salt, PASSWORD_ITERATIONS)}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_iter, raw_salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(raw_iter)
        salt = bytes.fromhex(raw_salt)
        actual = _derive(password, salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_code(code: str, salt: bytes) -> str:
    return _derive(code, salt, CODE_ITERATIONS)


@dataclass(frozen=True)
class UserAccount:
    id: str
    email: str
    name: str
    email_verified: bool

    def as_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "email_verified": self.email_verified}


class AccountStore:
    def __init__(self, path: Path, now=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or time.time
        self._lock = RLock()
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS one_time_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    purpose TEXT NOT NULL CHECK(purpose IN ('verify_email','reset_password')),
                    salt TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    consumed_at REAL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_codes_user_purpose ON one_time_codes(user_id, purpose, created_at DESC);
                CREATE TABLE IF NOT EXISTS device_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    revoked_at REAL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON device_sessions(user_id, expires_at);
                """
            )

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _normalize_email(email: str) -> str:
        value = (email or "").strip().lower()
        if len(value) > 254 or "@" not in value or value.startswith("@") or value.endswith("@"):
            raise AccountError("Informe um e-mail válido.")
        return value

    @staticmethod
    def _normalize_name(name: str) -> str:
        value = " ".join((name or "").strip().split())
        if not (2 <= len(value) <= 120):
            raise AccountError("Informe um nome entre 2 e 120 caracteres.")
        return value

    def _row_user(self, row) -> UserAccount:
        return UserAccount(str(row["id"]), str(row["email"]), str(row["name"]), bool(row["email_verified"]))

    def get_user(self, user_id: str) -> UserAccount | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT id,email,name,email_verified FROM users WHERE id=?", (user_id,)).fetchone()
        return self._row_user(row) if row else None

    def get_user_by_email(self, email: str) -> UserAccount | None:
        value = self._normalize_email(email)
        with self._lock, self._connect() as db:
            row = db.execute("SELECT id,email,name,email_verified FROM users WHERE email=?", (value,)).fetchone()
        return self._row_user(row) if row else None

    def register(self, name: str, email: str, password: str) -> UserAccount:
        email_n = self._normalize_email(email)
        name_n = self._normalize_name(name)
        pwd = _hash_password(password)
        user_id = str(uuid.uuid4())
        now = self._now()
        with self._lock, self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO users(id,email,name,password_hash,email_verified,created_at,updated_at) VALUES (?,?,?,?,0,?,?)",
                    (user_id, email_n, name_n, pwd, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise AccountError("Não foi possível criar a conta com esses dados.") from exc
        return UserAccount(user_id, email_n, name_n, False)

    def authenticate(self, email: str, password: str) -> UserAccount:
        email_n = self._normalize_email(email)
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email_n,)).fetchone()
        # Deliberately keep a generic credential error.
        if row is None or not _verify_password(password, str(row["password_hash"])):
            raise AccountError("E-mail ou senha inválidos.")
        user = self._row_user(row)
        if not user.email_verified:
            raise AccountError("Verifique seu e-mail antes de entrar.")
        return user

    def create_code(self, user_id: str, purpose: str, ttl_seconds: int = 600, min_interval_seconds: int = 60) -> str:
        if purpose not in {"verify_email", "reset_password"}:
            raise AccountError("Finalidade de código inválida.")
        alphabet = string.ascii_uppercase + string.digits
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        salt = secrets.token_bytes(16)
        now = self._now()
        with self._lock, self._connect() as db:
            latest = db.execute(
                "SELECT created_at FROM one_time_codes WHERE user_id=? AND purpose=? ORDER BY id DESC LIMIT 1",
                (user_id, purpose),
            ).fetchone()
            if latest is not None and now - float(latest["created_at"]) < min_interval_seconds:
                raise AccountError("Aguarde antes de solicitar um novo código.")
            db.execute(
                "UPDATE one_time_codes SET consumed_at=? WHERE user_id=? AND purpose=? AND consumed_at IS NULL",
                (now, user_id, purpose),
            )
            db.execute(
                "INSERT INTO one_time_codes(user_id,purpose,salt,code_hash,expires_at,created_at) VALUES (?,?,?,?,?,?)",
                (user_id, purpose, salt.hex(), _hash_code(code, salt), now + ttl_seconds, now),
            )
        return code

    def consume_code(self, email: str, code: str, purpose: str, max_attempts: int = 6) -> UserAccount:
        code = (code or "").strip().upper()
        if len(code) != 6 or not code.isalnum():
            raise AccountError("Código inválido ou expirado.")
        email_n = self._normalize_email(email)
        now = self._now()
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email_n,)).fetchone()
            if row is None:
                raise AccountError("Código inválido ou expirado.")
            code_row = db.execute(
                "SELECT * FROM one_time_codes WHERE user_id=? AND purpose=? AND consumed_at IS NULL ORDER BY id DESC LIMIT 1",
                (row["id"], purpose),
            ).fetchone()
            if code_row is None or float(code_row["expires_at"]) < now or int(code_row["attempts"]) >= max_attempts:
                raise AccountError("Código inválido ou expirado.")
            salt = bytes.fromhex(str(code_row["salt"]))
            ok = hmac.compare_digest(_hash_code(code, salt), str(code_row["code_hash"]))
            if not ok:
                db.execute("UPDATE one_time_codes SET attempts=attempts+1 WHERE id=?", (code_row["id"],))
                raise AccountError("Código inválido ou expirado.")
            db.execute("UPDATE one_time_codes SET consumed_at=? WHERE id=?", (now, code_row["id"]))
            if purpose == "verify_email":
                db.execute("UPDATE users SET email_verified=1, updated_at=? WHERE id=?", (now, row["id"]))
                row = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
        return self._row_user(row)

    def change_password_with_code(self, email: str, code: str, new_password: str) -> UserAccount:
        user = self.consume_code(email, code, "reset_password")
        pwd = _hash_password(new_password)
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id=?", (pwd, now, user.id))
            db.execute("UPDATE device_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now, user.id))
        return user

    def create_device_session(self, user_id: str, ttl_seconds: int = 60 * 60 * 24 * 30) -> tuple[str, str]:
        token = secrets.token_urlsafe(48)
        session_id = str(uuid.uuid4())
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO device_sessions(id,user_id,token_hash,created_at,expires_at) VALUES (?,?,?,?,?)",
                (session_id, user_id, _hash_token(token), now, now + ttl_seconds),
            )
        return session_id, token

    def validate_device_session(self, token: str) -> UserAccount | None:
        now = self._now()
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT u.id,u.email,u.name,u.email_verified FROM device_sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?",
                (_hash_token(token), now),
            ).fetchone()
        return self._row_user(row) if row else None

    def revoke_device_session(self, token: str) -> None:
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute("UPDATE device_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL", (now, _hash_token(token)))

    def revoke_all_sessions(self, user_id: str) -> None:
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute("UPDATE device_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now, user_id))

    def delete_user(self, user_id: str) -> bool:
        """Delete the account row and cascade account-owned auth records."""
        with self._lock, self._connect() as db:
            cur = db.execute("DELETE FROM users WHERE id=?", (user_id,))
            return cur.rowcount > 0
