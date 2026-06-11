"""SQLite-backed document store for Cleo (CONTRACTS §0).

Single `documents` table: (collection, id, payload JSON, created_at), WAL mode,
parameterized SQL only, no ORM. The DB path comes from the `CLEO_DB_PATH` env var
at construction time, overridable with an explicit `db_path` argument (tests).
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = "data/cleo.db"

# Id prefixes per CONTRACTS §0: <prefix>_<12 hex>
ID_PREFIXES = ("fb", "th", "bet", "act", "br", "dir", "run")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    collection TEXT NOT NULL,
    id         TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (collection, id)
)
"""


def new_id(prefix: str) -> str:
    """Generate an id like 'fb_3f9a1c2b4d5e' (prefix + 12 hex chars)."""
    return f"{prefix}_{secrets.token_hex(6)}"


def utc_now() -> str:
    """Current time as an ISO-8601 UTC string, e.g. '2026-06-12T09:30:00Z'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    """Document store over a single SQLite `documents` table (WAL, JSON payloads)."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = os.environ.get("CLEO_DB_PATH") or DEFAULT_DB_PATH
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + RLock: callers (FastAPI threadpool, FastMCP
        # event loop) may touch the same Store from different threads.
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    # -- CRUD ---------------------------------------------------------------

    def put(self, collection: str, id: str, doc: dict[str, Any]) -> None:
        """Upsert a document; row created_at is preserved on update."""
        payload = json.dumps(doc, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents (collection, id, payload, created_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(collection, id) DO UPDATE SET payload = excluded.payload",
                (collection, id, payload, utc_now()),
            )
            self._conn.commit()

    def get(self, collection: str, id: str) -> dict[str, Any] | None:
        """Return the document payload, or None if absent."""
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM documents WHERE collection = ? AND id = ?",
                (collection, id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list(
        self, collection: str, limit: int | None = None, **filters: Any
    ) -> list[dict[str, Any]]:
        """List documents with equality filters on payload fields (None matches JSON null/missing)."""
        sql = "SELECT payload FROM documents WHERE collection = ?"
        params: list[Any] = [collection]
        for key, value in filters.items():
            if not key.isidentifier():
                raise ValueError(f"invalid filter field: {key!r}")
            if value is None:
                sql += " AND json_extract(payload, ?) IS NULL"
                params.append(f"$.{key}")
            else:
                if isinstance(value, bool):
                    # SQLite json_extract surfaces JSON true/false as 1/0.
                    value = int(value)
                sql += " AND json_extract(payload, ?) = ?"
                params.extend([f"$.{key}", value])
        sql += " ORDER BY created_at ASC, id ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [json.loads(r[0]) for r in rows]

    def delete(self, collection: str, id: str) -> bool:
        """Delete a document; returns True if a row was removed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM documents WHERE collection = ? AND id = ?",
                (collection, id),
            )
            self._conn.commit()
        return cur.rowcount > 0

    # -- Helpers ------------------------------------------------------------

    def search_text(
        self,
        collection: str,
        query: str,
        fields: tuple[str, ...] = ("text",),
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Case-insensitive LIKE search across the given payload fields."""
        like = f"%{query.lower()}%"
        clause = " OR ".join(
            "LOWER(COALESCE(json_extract(payload, ?), '')) LIKE ?" for _ in fields
        )
        params: list[Any] = [collection]
        for field in fields:
            if not field.isidentifier():
                raise ValueError(f"invalid search field: {field!r}")
            params.extend([f"$.{field}", like])
        sql = (
            f"SELECT payload FROM documents WHERE collection = ? AND ({clause})"
            " ORDER BY created_at ASC, id ASC LIMIT ?"
        )
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [json.loads(r[0]) for r in rows]

    def count(self, collection: str) -> int:
        """Number of documents in a collection."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM documents WHERE collection = ?", (collection,)
            ).fetchone()
        return int(row[0])

    def close(self) -> None:
        """Close the underlying SQLite connection (releases file locks on Windows)."""
        with self._lock:
            self._conn.close()
