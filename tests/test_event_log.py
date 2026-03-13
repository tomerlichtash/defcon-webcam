#!/usr/bin/env python3
"""Tests for event log — error logging, JSON parsing, timestamps."""

import os
import re
import sys
import unittest

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)


class TestErrorLogging(unittest.TestCase):
    """Write operations in lib/ must log errors, not silently pass."""

    def _count_silent_except_in(self, filepath, write_fns):
        """Count 'except Exception: pass' in write-path functions."""
        with open(filepath) as f:
            source = f.read()
        silent = 0
        for fn_name in write_fns:
            fn_start = source.find(f"def {fn_name}(")
            if fn_start == -1:
                continue
            fn_end = source.find("\ndef ", fn_start + 1)
            if fn_end == -1:
                fn_end = len(source)
            fn_body = source[fn_start:fn_end]
            if re.search(r"except\s+Exception\s*:\s*\n\s*pass", fn_body):
                silent += 1
        return silent

    def test_event_log_writes_are_logged(self):
        """event_log write operations must not silently swallow errors."""
        path = os.path.join(_root, "lib", "event_log.py")
        silent = self._count_silent_except_in(path, ["log_event", "reset_db"])
        self.assertEqual(silent, 0,
                         f"event_log.py has {silent} silent exception handlers in write functions")

    def test_alert_log_writes_are_logged(self):
        """alert_log write operations must not silently swallow errors."""
        path = os.path.join(_root, "lib", "alert_log.py")
        silent = self._count_silent_except_in(path, ["log_event", "log_scan"])
        self.assertEqual(silent, 0,
                         f"alert_log.py has {silent} silent exception handlers in write functions")

    def test_state_save_is_logged(self):
        """save_state must not silently swallow errors."""
        path = os.path.join(_root, "lib", "state.py")
        silent = self._count_silent_except_in(path, ["save_state"])
        self.assertEqual(silent, 0,
                         "state.py save_state silently swallows write errors")


class TestEventLogJsonParsing(unittest.TestCase):
    """JSON parse errors in load_events must be logged, not silently swallowed."""

    def test_json_parse_errors_logged(self):
        """Individual event JSON parse failures should be logged."""
        path = os.path.join(_root, "lib", "event_log.py")
        with open(path) as f:
            source = f.read()
        fn_start = source.find("def load_events(")
        fn_end = source.find("\ndef ", fn_start + 1)
        fn_body = source[fn_start:fn_end]
        has_silent = re.search(r"except\s+Exception\s*:\s*\n\s*pass", fn_body)
        self.assertIsNone(has_silent,
                          "load_events silently swallows JSON parse errors")


class TestScanLogTimestamp(unittest.TestCase):
    """Scan log entries must include date for cross-day debugging."""

    def test_scan_log_has_date(self):
        """log_scan must use a timestamp format that includes the date."""
        path = os.path.join(_root, "lib", "alert_log.py")
        with open(path) as f:
            source = f.read()
        fn_start = source.find("def log_scan(")
        fn_end = source.find("\ndef ", fn_start + 1)
        if fn_end == -1:
            fn_end = len(source)
        fn_body = source[fn_start:fn_end]
        has_date = "%Y-%m-%d" in fn_body or "%Y" in fn_body
        self.assertTrue(has_date,
                        "log_scan uses time-only format (%H:%M:%S) — "
                        "must include date for cross-day debugging")


if __name__ == "__main__":
    unittest.main()
