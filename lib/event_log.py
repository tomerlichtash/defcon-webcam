"""Unified event log — SQLite-backed with 24h rolling window."""

import json
import os
import sqlite3
import time
import threading

DB_PATH = "/tmp/defcon-events.db"
MAX_AGE = 86400  # 24 hours
PAGE_SIZE = 200

_local = threading.local()


def _conn():
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_db():
    """Create tables and indexes if they don't exist."""
    conn = _conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            type TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_time ON events(time)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON events(type)")
    conn.commit()


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log_event(event_type, **kwargs):
    """Append an event to the database.

    event_type: 'alert', 'scan', 'status', 'system'
    kwargs: additional fields (message, defcon, source, result, label, value, raw, data)
             pass time_override to use a specific timestamp instead of now
    """
    ts = kwargs.pop("time_override", None) or _now()
    try:
        conn = _conn()
        conn.execute(
            "INSERT INTO events (time, type, data) VALUES (?, ?, ?)",
            (ts, event_type, json.dumps(kwargs, ensure_ascii=False))
        )
        conn.commit()
    except Exception:
        pass


def load_events(limit=PAGE_SIZE, since=None, offset=0):
    """Load events, newest first.

    limit: max number of events to return
    since: if set, only return events with time > since (for incremental polling)
    offset: skip this many events (for pagination)
    """
    try:
        conn = _conn()
        if since:
            rows = conn.execute(
                "SELECT id, time, type, data FROM events WHERE time > ? ORDER BY time DESC LIMIT ?",
                (since, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, time, type, data FROM events ORDER BY time DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        events = []
        for row in rows:
            entry = {"_type": row["type"], "time": row["time"], "_id": row["id"]}
            try:
                entry.update(json.loads(row["data"]))
            except Exception:
                pass
            events.append(entry)
        return events
    except Exception:
        return []


def count_events():
    """Return total number of events in the database."""
    try:
        conn = _conn()
        row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return row[0]
    except Exception:
        return 0


def reset_db():
    """Delete all events and vacuum the database."""
    try:
        conn = _conn()
        conn.execute("DELETE FROM events")
        conn.execute("VACUUM")
        conn.commit()
    except Exception:
        pass


def prune():
    """Remove entries older than 24 hours."""
    cutoff = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - MAX_AGE))
    try:
        conn = _conn()
        conn.execute("DELETE FROM events WHERE time < ?", (cutoff,))
        conn.commit()
    except Exception:
        pass


def migrate_from_jsonl(jsonl_path="/tmp/defcon-events.jsonl"):
    """One-time migration from JSONL to SQLite."""
    if not os.path.exists(jsonl_path):
        return 0
    count = 0
    try:
        conn = _conn()
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.pop("time", _now())
                    etype = entry.pop("_type", "status")
                    conn.execute(
                        "INSERT INTO events (time, type, data) VALUES (?, ?, ?)",
                        (ts, etype, json.dumps(entry, ensure_ascii=False))
                    )
                    count += 1
                except Exception:
                    continue
        conn.commit()
        # Rename old file so we don't re-import
        os.rename(jsonl_path, jsonl_path + ".migrated")
    except Exception:
        pass
    return count
