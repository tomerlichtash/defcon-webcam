#!/usr/bin/env python3
"""Tests for alert_log file I/O — log_event, load_log, log_scan, load_scan_log."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

import lib.alert_log as alert_log


class _AlertLogTestCase(unittest.TestCase):
    """Base class that redirects alert_log files to temp files."""

    def setUp(self):
        self._orig_log = alert_log.LOG_FILE
        self._orig_scan = alert_log.SCAN_LOG_FILE
        fd1, self._tmp_log = tempfile.mkstemp(suffix=".json")
        fd2, self._tmp_scan = tempfile.mkstemp(suffix=".json")
        os.close(fd1)
        os.close(fd2)
        # Start with empty files
        os.unlink(self._tmp_log)
        os.unlink(self._tmp_scan)
        alert_log.LOG_FILE = self._tmp_log
        alert_log.SCAN_LOG_FILE = self._tmp_scan

    def tearDown(self):
        alert_log.LOG_FILE = self._orig_log
        alert_log.SCAN_LOG_FILE = self._orig_scan
        for p in (self._tmp_log, self._tmp_scan):
            try:
                os.unlink(p)
            except OSError:
                pass


class TestLogEvent(_AlertLogTestCase):
    """Test alert log_event and load_log."""

    @patch("lib.alert_log._unified_log")
    def test_basic_write_and_read(self, _):
        alert_log.log_event("DEFCON 2")
        entries = alert_log.load_log()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["defcon"], "DEFCON 2")
        self.assertIn("time", entries[0])

    @patch("lib.alert_log._unified_log")
    def test_with_raw_data(self, _):
        raw = {"title": "ירי רקטות", "data": ["תל אביב"]}
        alert_log.log_event("DEFCON 2", raw_data=raw)
        entries = alert_log.load_log()
        self.assertEqual(entries[0]["raw"]["title"], "ירי רקטות")

    @patch("lib.alert_log._unified_log")
    def test_newest_first(self, _):
        alert_log.log_event("DEFCON 4")
        alert_log.log_event("DEFCON 2")
        entries = alert_log.load_log()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["defcon"], "DEFCON 2")

    @patch("lib.alert_log._unified_log")
    def test_max_entries_cap(self, _):
        for i in range(alert_log.MAX_ENTRIES + 10):
            alert_log.log_event(f"event {i}")
        entries = alert_log.load_log()
        self.assertEqual(len(entries), alert_log.MAX_ENTRIES)

    def test_load_missing_file(self):
        alert_log.LOG_FILE = "/tmp/nonexistent-alert-log.json"
        entries = alert_log.load_log()
        self.assertEqual(entries, [])

    @patch("lib.alert_log._unified_log")
    def test_calls_unified_log(self, mock_unified):
        alert_log.log_event("DEFCON 2", raw_data={"data": ["test"]})
        mock_unified.assert_called_once_with(
            "alert", defcon="DEFCON 2", raw={"data": ["test"]}
        )


class TestLogScan(_AlertLogTestCase):
    """Test scan log_scan and load_scan_log."""

    @patch("lib.alert_log._unified_log")
    def test_basic_scan(self, _):
        alert_log.log_scan("primary", '{"data":[]}', "none")
        entries = alert_log.load_scan_log()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "primary")
        self.assertEqual(entries[0]["result"], "none")

    @patch("lib.alert_log._unified_log")
    def test_truncates_raw_text(self, _):
        long_text = "x" * 1000
        alert_log.log_scan("primary", long_text, "none")
        entries = alert_log.load_scan_log()
        self.assertEqual(len(entries[0]["data"]), 500)

    @patch("lib.alert_log._unified_log")
    def test_none_raw_text(self, _):
        alert_log.log_scan("primary", None, "error")
        entries = alert_log.load_scan_log()
        self.assertEqual(entries[0]["data"], "")

    @patch("lib.alert_log._unified_log")
    def test_max_scan_entries_cap(self, _):
        for i in range(alert_log.MAX_SCAN_ENTRIES + 10):
            alert_log.log_scan("primary", f"data {i}", "none")
        entries = alert_log.load_scan_log()
        self.assertEqual(len(entries), alert_log.MAX_SCAN_ENTRIES)

    def test_load_missing_scan_file(self):
        alert_log.SCAN_LOG_FILE = "/tmp/nonexistent-scan-log.json"
        entries = alert_log.load_scan_log()
        self.assertEqual(entries, [])

    @patch("lib.alert_log._unified_log")
    def test_scan_has_date_in_timestamp(self, _):
        """Scan log timestamps must include date, not just time."""
        alert_log.log_scan("primary", "{}", "none")
        entries = alert_log.load_scan_log()
        ts = entries[0]["time"]
        # Should be YYYY-MM-DD HH:MM:SS format
        self.assertRegex(ts, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


if __name__ == "__main__":
    unittest.main()
