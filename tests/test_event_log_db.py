#!/usr/bin/env python3
"""Tests for event_log SQLite operations — init, write, read, prune, migrate."""

import json
import os
import sys
import tempfile
import threading
import unittest

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

import lib.event_log as event_log


class _DBTestCase(unittest.TestCase):
    """Base class that redirects event_log to a temp DB per test."""

    def setUp(self):
        self._orig_path = event_log.DB_PATH
        fd, self._tmpdb = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        event_log.DB_PATH = self._tmpdb
        # Clear thread-local connection so it reconnects to temp DB
        if hasattr(event_log._local, "conn"):
            del event_log._local.conn
        event_log.init_db()

    def tearDown(self):
        if hasattr(event_log._local, "conn"):
            event_log._local.conn.close()
            del event_log._local.conn
        event_log.DB_PATH = self._orig_path
        try:
            os.unlink(self._tmpdb)
        except OSError:
            pass


class TestInitDb(_DBTestCase):
    """init_db creates tables and indexes."""

    def test_creates_events_table(self):
        conn = event_log._conn()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_creates_indexes(self):
        conn = event_log._conn()
        indexes = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        ]
        self.assertIn("idx_time", indexes)
        self.assertIn("idx_type", indexes)

    def test_idempotent(self):
        """Calling init_db twice should not error."""
        event_log.init_db()
        event_log.init_db()


class TestLogEvent(_DBTestCase):
    """log_event inserts events correctly."""

    def test_basic_insert(self):
        event_log.log_event("alert", message="test alert")
        events = event_log.load_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["_type"], "alert")
        self.assertEqual(events[0]["message"], "test alert")

    def test_multiple_types(self):
        event_log.log_event("alert", message="a")
        event_log.log_event("scan", source="primary")
        event_log.log_event("system", label="startup")
        self.assertEqual(event_log.count_events(), 3)

    def test_time_override(self):
        event_log.log_event("status", value="ok", time_override="2025-01-01 00:00:00")
        events = event_log.load_events()
        self.assertEqual(events[0]["time"], "2025-01-01 00:00:00")

    def test_unicode_data(self):
        event_log.log_event("alert", message="תל אביב - התרעה")
        events = event_log.load_events()
        self.assertIn("תל אביב", events[0]["message"])


class TestLoadEvents(_DBTestCase):
    """load_events with filtering, pagination, and since."""

    def _insert_events(self, n):
        for i in range(n):
            event_log.log_event(
                "alert",
                message=f"event {i}",
                time_override=f"2025-01-01 00:00:{i:02d}",
            )

    def test_newest_first(self):
        self._insert_events(3)
        events = event_log.load_events()
        self.assertEqual(events[0]["message"], "event 2")
        self.assertEqual(events[2]["message"], "event 0")

    def test_limit(self):
        self._insert_events(10)
        events = event_log.load_events(limit=3)
        self.assertEqual(len(events), 3)

    def test_offset(self):
        self._insert_events(5)
        events = event_log.load_events(limit=2, offset=2)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["message"], "event 2")

    def test_since(self):
        self._insert_events(5)
        events = event_log.load_events(since="2025-01-01 00:00:02")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["message"], "event 4")

    def test_empty_db(self):
        events = event_log.load_events()
        self.assertEqual(events, [])

    def test_malformed_json_includes_parse_error(self):
        """Rows with bad JSON in data column should include _parse_error."""
        conn = event_log._conn()
        conn.execute(
            "INSERT INTO events (time, type, data) VALUES (?, ?, ?)",
            ("2025-01-01 00:00:00", "alert", "{bad json"),
        )
        conn.commit()
        events = event_log.load_events()
        self.assertEqual(len(events), 1)
        self.assertIn("_parse_error", events[0])


class TestCountEvents(_DBTestCase):
    """count_events returns correct count."""

    def test_empty(self):
        self.assertEqual(event_log.count_events(), 0)

    def test_after_inserts(self):
        event_log.log_event("alert", message="a")
        event_log.log_event("scan", source="b")
        self.assertEqual(event_log.count_events(), 2)


class TestResetDb(_DBTestCase):
    """reset_db clears all events."""

    def test_reset_clears_events(self):
        event_log.log_event("alert", message="a")
        event_log.log_event("scan", source="b")
        self.assertEqual(event_log.count_events(), 2)
        event_log.reset_db()
        self.assertEqual(event_log.count_events(), 0)


class TestPrune(_DBTestCase):
    """prune removes events older than MAX_AGE."""

    def test_removes_old_events(self):
        event_log.log_event("alert", message="old", time_override="2020-01-01 00:00:00")
        event_log.log_event("alert", message="new")
        self.assertEqual(event_log.count_events(), 2)
        event_log.prune()
        self.assertEqual(event_log.count_events(), 1)
        events = event_log.load_events()
        self.assertEqual(events[0]["message"], "new")


class TestMigrateFromJsonl(_DBTestCase):
    """migrate_from_jsonl imports JSONL data into SQLite."""

    def test_migrates_entries(self):
        fd, jsonl_path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({"time": "2025-01-01 00:00:00", "_type": "alert", "message": "migrated"}) + "\n")
            f.write(json.dumps({"time": "2025-01-01 00:00:01", "_type": "scan", "source": "test"}) + "\n")
        try:
            count = event_log.migrate_from_jsonl(jsonl_path)
            self.assertEqual(count, 2)
            self.assertEqual(event_log.count_events(), 2)
            # Original file should be renamed
            self.assertFalse(os.path.exists(jsonl_path))
            self.assertTrue(os.path.exists(jsonl_path + ".migrated"))
        finally:
            for p in (jsonl_path, jsonl_path + ".migrated"):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_missing_file_returns_zero(self):
        count = event_log.migrate_from_jsonl("/tmp/nonexistent-jsonl-file.jsonl")
        self.assertEqual(count, 0)

    def test_skips_blank_lines(self):
        fd, jsonl_path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as f:
            f.write("\n")
            f.write(json.dumps({"_type": "alert", "message": "ok"}) + "\n")
            f.write("\n")
        try:
            count = event_log.migrate_from_jsonl(jsonl_path)
            self.assertEqual(count, 1)
        finally:
            for p in (jsonl_path, jsonl_path + ".migrated"):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_skips_malformed_lines(self):
        fd, jsonl_path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as f:
            f.write("{bad json\n")
            f.write(json.dumps({"_type": "alert", "message": "good"}) + "\n")
        try:
            count = event_log.migrate_from_jsonl(jsonl_path)
            self.assertEqual(count, 1)
        finally:
            for p in (jsonl_path, jsonl_path + ".migrated"):
                try:
                    os.unlink(p)
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
