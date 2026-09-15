from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    owner_key TEXT NOT NULL,
    title TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_owner_updated
    ON projects(owner_key, updated_at DESC);

CREATE TABLE IF NOT EXISTS support_requests (
    id TEXT PRIMARY KEY,
    owner_key TEXT NOT NULL,
    project_id TEXT,
    page_number INTEGER,
    step TEXT,
    contact TEXT,
    message TEXT NOT NULL,
    context_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_support_created
    ON support_requests(created_at DESC);

CREATE TABLE IF NOT EXISTS consent_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_key TEXT NOT NULL,
    document_slug TEXT NOT NULL,
    document_version TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_codes (
    email TEXT PRIMARY KEY,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def save_project(self, project_id: str, owner_key: str, title: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self.connect() as connection:
            existing = connection.execute("SELECT created_at FROM projects WHERE id = ?", (project_id,)).fetchone()
            created_at = existing["created_at"] if existing else now
            connection.execute(
                """INSERT INTO projects(id, owner_key, title, payload_json, created_at, updated_at)
                   VALUES(?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     owner_key=excluded.owner_key,
                     title=excluded.title,
                     payload_json=excluded.payload_json,
                     updated_at=excluded.updated_at""",
                (project_id, owner_key, title, encoded, created_at, now),
            )
        return {"id": project_id, "title": title, "created_at": created_at, "updated_at": now}

    def list_projects(self, owner_key: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, title, payload_json, created_at, updated_at FROM projects WHERE owner_key = ? ORDER BY updated_at DESC",
                (owner_key,),
            ).fetchall()
        return [
            {
                "id": row["id"], "title": row["title"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"], "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def get_project(self, project_id: str, owner_key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, title, payload_json, created_at, updated_at FROM projects WHERE id = ? AND owner_key = ?",
                (project_id, owner_key),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"], "title": row["title"],
            "payload": json.loads(row["payload_json"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    def create_support_request(self, item: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO support_requests(
                       id, owner_key, project_id, page_number, step, contact,
                       message, context_json, status, created_at
                   ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
                (
                    item["id"], item["owner_key"], item.get("project_id"), item.get("page_number"),
                    item.get("step"), item.get("contact"), item["message"],
                    json.dumps(item.get("context", {}), ensure_ascii=False), item["created_at"],
                ),
            )

    def save_consent(self, owner_key: str, slug: str, version: str, accepted: bool, source: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO consent_events(owner_key, document_slug, document_version, accepted, source, created_at) VALUES(?, ?, ?, ?, ?, ?)",
                (owner_key, slug, version, int(accepted), source, utc_now()),
            )

    def save_email_code(self, email: str, code_hash: str, expires_at: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO email_codes(email, code_hash, expires_at, attempts, created_at)
                   VALUES(?, ?, ?, 0, ?)
                   ON CONFLICT(email) DO UPDATE SET code_hash=excluded.code_hash,
                     expires_at=excluded.expires_at, attempts=0, created_at=excluded.created_at""",
                (email, code_hash, expires_at, now),
            )

    def get_email_code(self, email: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT code_hash, expires_at, attempts FROM email_codes WHERE email = ?", (email,)
            ).fetchone()
        return dict(row) if row else None

    def increment_email_attempts(self, email: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE email_codes SET attempts = attempts + 1 WHERE email = ?", (email,))

    def consume_email_code(self, email: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM email_codes WHERE email = ?", (email,))

    def get_or_create_user(self, email: str) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute("SELECT id, email FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                connection.execute("UPDATE users SET updated_at = ? WHERE id = ?", (now, row["id"]))
                return dict(row)
            user_id = "usr_" + __import__("secrets").token_hex(12)
            connection.execute(
                "INSERT INTO users(id, email, created_at, updated_at) VALUES(?, ?, ?, ?)",
                (user_id, email, now, now),
            )
        return {"id": user_id, "email": email}

    def save_session(self, token_hash: str, user_id: str, expires_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES(?, ?, ?, ?)",
                (token_hash, user_id, expires_at, utc_now()),
            )

    def get_session_user(self, token_hash: str, now: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT users.id, users.email FROM sessions
                   JOIN users ON users.id = sessions.user_id
                   WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
                (token_hash, now),
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
