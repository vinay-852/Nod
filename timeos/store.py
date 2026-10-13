"""SQLite storage only — events, deadlines, meta. No domain logic (see scheduling.py)."""

from __future__ import annotations

import functools
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'event',
  notes TEXT NOT NULL DEFAULT '',
  deadline_id INTEGER,
  google_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deadlines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  due TEXT NOT NULL,
  context TEXT NOT NULL DEFAULT '',
  effort_hours REAL NOT NULL DEFAULT 0,
  hours_logged REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

_EVENT_FIELDS = ("title", "start_ts", "end_ts", "kind", "notes", "deadline_id", "google_id")
_DEADLINE_FIELDS = ("title", "due", "context", "effort_hours", "hours_logged", "status")


def _locked(fn):
    """Run a store method under the connection lock (tools run in a thread pool)."""

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)

    return wrapper


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()  # reentrant: store methods call each other
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- events ----------

    @_locked
    def add_event(self, title, start_ts, end_ts, kind="event", notes="", deadline_id=None, google_id=None) -> dict:
        cur = self.conn.execute(
            "INSERT INTO events (title, start_ts, end_ts, kind, notes, deadline_id, google_id, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))",
            (title, start_ts, end_ts, kind, notes, deadline_id, google_id),
        )
        self.conn.commit()
        return self.get_event(cur.lastrowid)

    @_locked
    def update_event(self, event_id: int, **fields) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in _EVENT_FIELDS and v is not None}
        if allowed:
            sets = ", ".join(f"{k}=?" for k in allowed)
            self.conn.execute(f"UPDATE events SET {sets}, updated_at=datetime('now','localtime') WHERE id=?",
                              (*allowed.values(), event_id))
            self.conn.commit()
        return self.get_event(event_id)

    @_locked
    def delete_event(self, event_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        self.conn.commit()
        return cur.rowcount > 0

    @_locked
    def get_event(self, event_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        return dict(row) if row else None

    @_locked
    def list_events(self, start_ts: str | None = None, end_ts: str | None = None, kind: str | None = None) -> list[dict]:
        """Events in the half-open window [start_ts, end_ts) — i.e. events overlapping it."""
        q, args = "SELECT * FROM events WHERE 1=1", []
        if start_ts:
            q += " AND end_ts > ?"
            args.append(start_ts)
        if end_ts:
            q += " AND start_ts < ?"
            args.append(end_ts)
        if kind:
            q += " AND kind = ?"
            args.append(kind)
        q += " ORDER BY start_ts"
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    # ---------- deadlines ----------

    @_locked
    def add_deadline(self, title, due, context="", effort_hours=0.0) -> dict:
        cur = self.conn.execute(
            "INSERT INTO deadlines (title, due, context, effort_hours, hours_logged, status, created_at, updated_at)"
            " VALUES (?,?,?,?,0,'open',datetime('now','localtime'),datetime('now','localtime'))",
            (title, due, context, float(effort_hours)),
        )
        self.conn.commit()
        return self.get_deadline(cur.lastrowid)

    @_locked
    def get_deadline(self, deadline_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM deadlines WHERE id=?", (deadline_id,)).fetchone()
        return dict(row) if row else None

    @_locked
    def update_deadline(self, deadline_id: int, **fields) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in _DEADLINE_FIELDS and v is not None}
        if allowed:
            sets = ", ".join(f"{k}=?" for k in allowed)
            self.conn.execute(f"UPDATE deadlines SET {sets}, updated_at=datetime('now','localtime') WHERE id=?",
                              (*allowed.values(), deadline_id))
            self.conn.commit()
        return self.get_deadline(deadline_id)

    @_locked
    def list_deadlines(self, status: str | None = None, due_before: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM deadlines WHERE 1=1", []
        if status:
            q += " AND status = ?"
            args.append(status)
        if due_before:
            q += " AND due <= ?"
            args.append(due_before)
        q += " ORDER BY due"
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    @_locked
    def log_study_hours(self, deadline_id: int | None, minutes: int) -> dict | None:
        """Credit focused study minutes toward a deadline's hours_logged."""
        if deadline_id is None:
            return None
        self.conn.execute(
            "UPDATE deadlines SET hours_logged = hours_logged + ?, updated_at=datetime('now','localtime') WHERE id=?",
            (float(minutes) / 60, deadline_id),
        )
        self.conn.commit()
        return self.get_deadline(deadline_id)

    # ---------- meta ----------

    @_locked
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    @_locked
    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()