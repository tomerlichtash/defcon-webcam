#!/usr/bin/env python3
"""Tests for HIGH/MEDIUM priority fixes (TDD — written to verify fixes)."""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)


# ---------------------------------------------------------------------------
# 1. Input validation — simulate count clamping
# ---------------------------------------------------------------------------


class TestSimulateCountValidation(unittest.TestCase):
    """The simulate command must clamp count to 1–1000 and handle bad input."""

    def _get_simulate_block(self):
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()
        # Find the first simulate block (in /api handler)
        import re
        m = re.search(r'if cmd == ["\']simulate["\']:', source)
        self.assertIsNotNone(m, "simulate block not found")
        # Extract until the next 'return'
        block_start = m.start()
        block_end = source.find("return", block_start)
        return source[block_start:block_end]

    def test_negative_count_is_clamped(self):
        """Negative count values must be clamped to at least 1."""
        block = self._get_simulate_block()
        # Must have bounds clamping — max(1, ...) or similar
        has_lower_bound = "max(1" in block or "max( 1" in block
        self.assertTrue(has_lower_bound,
                        "simulate count has no lower bound — negative values pass through")

    def test_huge_count_is_clamped(self):
        """Very large count values must be capped."""
        block = self._get_simulate_block()
        has_upper_bound = "min(" in block and "1000" in block
        self.assertTrue(has_upper_bound,
                        "simulate count has no upper bound — huge values pass through")

    def test_non_numeric_count_is_handled(self):
        """Non-numeric count values must not crash the server."""
        block = self._get_simulate_block()
        has_error_handling = "ValueError" in block or "except" in block
        self.assertTrue(has_error_handling,
                        "simulate count has no error handling for non-numeric input")


# ---------------------------------------------------------------------------
# 2. Input validation — defcon command missing level
# ---------------------------------------------------------------------------


class TestDefconMissingLevel(unittest.TestCase):
    """'defcon ' with no level must not crash with IndexError."""

    def test_defcon_split_is_safe(self):
        """cmd.split()[1] must be guarded against IndexError."""
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()

        import re
        # Find the defcon command handler in /api block
        api_start = re.search(r'if self\.path\.startswith\(["\']\/api', source)
        admin_start = re.search(r'elif self\.path\.startswith\(["\']\/admin\/api', source)
        api_block = source[api_start.start():admin_start.start()]

        defcon_start = re.search(r'cmd\.startswith\(["\']defcon ', api_block)
        self.assertIsNotNone(defcon_start, "defcon handler not found")

        # Extract the defcon handler block (next ~40 lines)
        defcon_block = api_block[defcon_start.start():defcon_start.start() + 800]

        # Must NOT use cmd.split()[1] without a length check
        has_unsafe_split = "cmd.split()[1]" in defcon_block
        has_safe_split = "len(parts)" in defcon_block or "len(cmd.split())" in defcon_block

        self.assertFalse(has_unsafe_split and not has_safe_split,
                         "defcon handler uses cmd.split()[1] without bounds check — "
                         "IndexError on 'defcon ' with no level")


# ---------------------------------------------------------------------------
# 3. Input validation — camctl command missing action
# ---------------------------------------------------------------------------


class TestCamctlMissingAction(unittest.TestCase):
    """'camctl ' with no action must not crash with IndexError."""

    def test_camctl_split_is_safe(self):
        """cmd.split()[1] must be guarded against IndexError."""
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()

        import re
        api_start = re.search(r'if self\.path\.startswith\(["\']\/api', source)
        admin_start = re.search(r'elif self\.path\.startswith\(["\']\/admin\/api', source)
        api_block = source[api_start.start():admin_start.start()]

        camctl_start = re.search(r'cmd\.startswith\(["\']camctl ', api_block)
        self.assertIsNotNone(camctl_start, "camctl handler not found")

        camctl_block = api_block[camctl_start.start():camctl_start.start() + 400]

        has_unsafe_split = "cmd.split()[1]" in camctl_block
        has_safe_split = ("len(parts)" in camctl_block or
                          "len(cmd.split())" in camctl_block or
                          "if len(" in camctl_block)

        self.assertFalse(has_unsafe_split and not has_safe_split,
                         "camctl handler uses cmd.split()[1] without bounds check — "
                         "IndexError on 'camctl ' with no action")


# ---------------------------------------------------------------------------
# 4. Geocode DB — context managers prevent connection leaks
# ---------------------------------------------------------------------------


class TestGeocodeContextManagers(unittest.TestCase):
    """All geocode DB operations must use context managers (with _conn())."""

    def test_no_manual_conn_close(self):
        """There should be no manual conn.close() calls — use 'with' instead."""
        geo_path = os.path.join(_root, "lib", "geocode.py")
        with open(geo_path) as f:
            source = f.read()

        # conn.close() indicates manual connection management (leak-prone)
        close_count = source.count("conn.close()")
        self.assertEqual(close_count, 0,
                         f"geocode.py has {close_count} manual conn.close() calls — "
                         "should use 'with _conn() as conn:' context manager instead")

    def test_uses_context_manager(self):
        """DB functions must use 'with _conn()' pattern."""
        geo_path = os.path.join(_root, "lib", "geocode.py")
        with open(geo_path) as f:
            source = f.read()

        # Count 'with _conn()' usages — should be in every function that accesses DB
        context_count = source.count("with _conn()")
        # init_geo_db, city_count, lookup, lookup_fuzzy, random_cities, populate_from_overpass
        self.assertGreaterEqual(context_count, 6,
                                f"Only {context_count} 'with _conn()' usages — "
                                "expected at least 6 (one per DB function)")


# ---------------------------------------------------------------------------
# 5. Geocode DB — functional tests
# ---------------------------------------------------------------------------


class TestGeocodeFunctions(unittest.TestCase):
    """Test geocode lookup functions with a temporary DB."""

    @classmethod
    def setUpClass(cls):
        cls._orig_path = None
        # Create a temp DB
        cls._tmpdb = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmpdb.close()
        # Patch GEO_DB_PATH
        import lib.geocode as geo
        cls._orig_path = geo.GEO_DB_PATH
        geo.GEO_DB_PATH = cls._tmpdb.name
        geo.init_geo_db()
        # Insert test data
        conn = sqlite3.connect(cls._tmpdb.name)
        conn.execute(
            "INSERT INTO cities (name, name_he, lat, lng, source) VALUES (?, ?, ?, ?, ?)",
            ("Tel Aviv", "תל אביב", 32.08, 34.78, "test"),
        )
        conn.execute(
            "INSERT INTO cities (name, name_he, lat, lng, source) VALUES (?, ?, ?, ?, ?)",
            ("Haifa", "חיפה", 32.79, 34.99, "test"),
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        import lib.geocode as geo
        geo.GEO_DB_PATH = cls._orig_path
        os.unlink(cls._tmpdb.name)

    def test_city_count(self):
        from lib.geocode import city_count
        self.assertEqual(city_count(), 2)

    def test_lookup_exact(self):
        from lib.geocode import lookup
        result = lookup("תל אביב")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Tel Aviv")
        self.assertAlmostEqual(result["lat"], 32.08)

    def test_lookup_not_found(self):
        from lib.geocode import lookup
        result = lookup("nonexistent")
        self.assertIsNone(result)

    def test_lookup_fuzzy(self):
        from lib.geocode import lookup_fuzzy
        result = lookup_fuzzy("תל אביב - מרכז")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Tel Aviv")

    def test_lookup_many(self):
        from lib.geocode import lookup_many
        results = lookup_many(["תל אביב", "חיפה", "nonexistent"])
        self.assertEqual(len(results), 2)

    def test_random_cities(self):
        from lib.geocode import random_cities
        results = random_cities(10)
        self.assertEqual(len(results), 2)  # only 2 in DB


# ---------------------------------------------------------------------------
# 6. Sysinfo — deduped helpers
# ---------------------------------------------------------------------------


class TestSysinfoHelpers(unittest.TestCase):
    """Test extracted _defcon_from_state and _alert_cities helpers."""

    def test_defcon_from_state_defcon2(self):
        from lib.sysinfo import _defcon_from_state
        self.assertEqual(_defcon_from_state("defcon2"), 2)

    def test_defcon_from_state_defcon4(self):
        from lib.sysinfo import _defcon_from_state
        self.assertEqual(_defcon_from_state("defcon4"), 4)

    def test_defcon_from_state_idle(self):
        from lib.sysinfo import _defcon_from_state
        self.assertEqual(_defcon_from_state("idle"), 5)

    def test_defcon_from_state_unknown(self):
        from lib.sysinfo import _defcon_from_state
        self.assertEqual(_defcon_from_state("bogus"), 5)

    @patch("lib.sysinfo.load_log", return_value=[])
    def test_alert_cities_empty_log(self, _mock):
        from lib.sysinfo import _alert_cities
        result = _alert_cities()
        self.assertIsNone(result)

    @patch("lib.sysinfo.lookup_many", return_value=[{"name": "Tel Aviv", "name_he": "תל אביב", "lat": 32.08, "lng": 34.78}])
    @patch("lib.sysinfo.load_log", return_value=[{"raw": {"data": ["תל אביב"]}}])
    def test_alert_cities_with_data(self, _mock_log, _mock_lookup):
        from lib.sysinfo import _alert_cities
        result = _alert_cities()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Tel Aviv")

    @patch("lib.sysinfo.load_log", return_value=[{"raw": {"data": "single city"}}])
    @patch("lib.sysinfo.lookup_many", return_value=[])
    def test_alert_cities_string_data(self, _mock_lookup, _mock_log):
        """data field as string (not list) must be wrapped in a list."""
        from lib.sysinfo import _alert_cities
        _alert_cities()
        # Verify lookup_many was called with a list
        _mock_lookup.assert_called_once_with(["single city"])


# ---------------------------------------------------------------------------
# 7. Camera helper — _camera_ctl exists and handles errors
# ---------------------------------------------------------------------------


class TestCameraCtlHelper(unittest.TestCase):
    """_camera_ctl must exist as a helper and handle subprocess failures."""

    def test_camera_ctl_function_exists(self):
        """_camera_ctl should be defined as a standalone helper."""
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()
        self.assertIn("def _camera_ctl(", source,
                       "_camera_ctl helper not found — camera subprocess calls still inlined")

    def test_camera_ctl_handles_exceptions(self):
        """_camera_ctl must catch subprocess exceptions."""
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()
        fn_start = source.find("def _camera_ctl(")
        fn_end = source.find("\ndef ", fn_start + 1)
        fn_body = source[fn_start:fn_end]
        self.assertIn("except", fn_body,
                       "_camera_ctl has no exception handling — subprocess failures will crash")

    def test_defcon_commands_use_camera_ctl(self):
        """Defcon set commands must use _camera_ctl, not inline subprocess."""
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()

        import re
        api_start = re.search(r'if self\.path\.startswith\(["\']\/api', source)
        admin_start = re.search(r'elif self\.path\.startswith\(["\']\/admin\/api', source)
        api_block = source[api_start.start():admin_start.start()]

        defcon_start = re.search(r'cmd\.startswith\(["\']defcon ', api_block)
        defcon_block = api_block[defcon_start.start():defcon_start.start() + 1200]

        # Should use _camera_ctl, not inline subprocess.run for mjpg-streamer
        has_inline_subprocess = "systemctl" in defcon_block and "mjpg-streamer" in defcon_block
        has_helper_call = "_camera_ctl(" in defcon_block

        self.assertTrue(has_helper_call,
                        "defcon commands don't use _camera_ctl helper")
        self.assertFalse(has_inline_subprocess,
                         "defcon commands still have inline subprocess calls for camera")


# ---------------------------------------------------------------------------
# 8. Error logging — write operations must not silently swallow errors
# ---------------------------------------------------------------------------


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
            # Check for bare 'except Exception:\n        pass'
            import re
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


# ---------------------------------------------------------------------------
# 9. Dead code removed — mjpg-alert tweet delay loop
# ---------------------------------------------------------------------------


class TestAlertDeadCodeRemoved(unittest.TestCase):
    """The disabled tweet delay loop must be removed from mjpg-alert."""

    def test_no_tweet_delay_loop(self):
        """The 5-iteration tweet delay loop should not exist when publish is disabled."""
        alert_path = os.path.join(_root, "bin", "mjpg-alert")
        with open(alert_path) as f:
            source = f.read()
        self.assertNotIn("tweet_cancelled", source,
                         "Dead tweet delay loop still present in mjpg-alert")

    def test_unused_imports_removed(self):
        """post_tweet and post_telegram should not be imported when unused."""
        alert_path = os.path.join(_root, "bin", "mjpg-alert")
        with open(alert_path) as f:
            source = f.read()
        self.assertNotIn("post_tweet", source,
                         "Unused post_tweet import still in mjpg-alert")
        self.assertNotIn("post_telegram", source,
                         "Unused post_telegram import still in mjpg-alert")


# ---------------------------------------------------------------------------
# 10. Empty quotes must not crash server
# ---------------------------------------------------------------------------


class TestEmptyQuotesSafe(unittest.TestCase):
    """Empty quotes list must not cause randrange(0) ValueError."""

    def test_empty_quotes_returns_empty(self):
        """When quotes list is empty, server should return empty quote, not crash."""
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()
        import re
        m = re.search(r'if cmd == ["\']quote["\']:', source)
        self.assertIsNotNone(m, "quote handler not found")
        block = source[m.start():m.start() + 600]
        # Must check if quotes is non-empty before randrange
        has_guard = "if quotes:" in block or "if len(quotes)" in block or "if not quotes" in block
        self.assertTrue(has_guard,
                        "quote handler calls randrange without checking for empty list")


# ---------------------------------------------------------------------------
# 11. Atomic state writes — write-then-rename pattern
# ---------------------------------------------------------------------------


class TestAtomicStateWrite(unittest.TestCase):
    """save_state must use atomic write (temp file + rename) to prevent corruption."""

    def test_save_state_is_atomic(self):
        """save_state should write to a temp file and rename, not write directly."""
        path = os.path.join(_root, "lib", "state.py")
        with open(path) as f:
            source = f.read()
        fn_start = source.find("def save_state(")
        fn_end = source.find("\ndef ", fn_start + 1)
        if fn_end == -1:
            fn_end = len(source)
        fn_body = source[fn_start:fn_end]
        # Must use os.rename or os.replace for atomicity
        has_atomic = "os.replace(" in fn_body or "os.rename(" in fn_body
        self.assertTrue(has_atomic,
                        "save_state writes directly to state file — "
                        "should use temp file + os.replace for atomicity")


# ---------------------------------------------------------------------------
# 12. Oref API backoff on repeated failures
# ---------------------------------------------------------------------------


class TestOrefBackoff(unittest.TestCase):
    """Oref API client must back off on repeated failures."""

    def test_has_failure_tracking(self):
        """oref.py must track consecutive failures for backoff."""
        path = os.path.join(_root, "lib", "oref.py")
        with open(path) as f:
            source = f.read()
        has_backoff = ("_fail_count" in source or "_consecutive_fail" in source
                       or "backoff" in source or "_errors" in source)
        self.assertTrue(has_backoff,
                        "oref.py has no failure tracking — polls at full rate even during outages")


# ---------------------------------------------------------------------------
# 13. Camera stream listener cleanup
# ---------------------------------------------------------------------------


class TestStreamListenerCleanup(unittest.TestCase):
    """initCamera() must clean up previous event listeners to prevent stacking."""

    def test_removes_old_error_listener(self):
        """initCamera must remove or guard against duplicate error listeners."""
        cam_path = os.path.join(_root, "static", "js", "camera.js")
        with open(cam_path) as f:
            source = f.read()
        fn_start = source.find("initCamera()")
        fn_end = source.find("\n  },", fn_start)
        fn_body = source[fn_start:fn_end]
        # Must either use { once: true }, removeEventListener, or a guard flag
        has_cleanup = ("removeEventListener" in fn_body
                       or "_errorListenerAdded" in fn_body
                       or "once:" in fn_body
                       or "._errorHandler" in fn_body)
        self.assertTrue(has_cleanup,
                        "initCamera adds error listeners without cleanup — "
                        "multiple calls will stack duplicate listeners")


# ---------------------------------------------------------------------------
# 14. Config parsing must log errors
# ---------------------------------------------------------------------------


class TestConfigLogging(unittest.TestCase):
    """_parse_conf must log errors, not silently return empty dict."""

    def test_parse_conf_logs_errors(self):
        """_parse_conf should log when config file is malformed."""
        path = os.path.join(_root, "lib", "config.py")
        with open(path) as f:
            source = f.read()
        fn_start = source.find("def _parse_conf(")
        fn_end = source.find("\ndef ", fn_start + 1)
        fn_body = source[fn_start:fn_end]
        import re
        has_silent = re.search(r"except\s+Exception\s*:\s*\n\s*pass", fn_body)
        self.assertIsNone(has_silent,
                          "_parse_conf silently swallows all errors — "
                          "should at least log FileNotFoundError vs parse errors")


# ---------------------------------------------------------------------------
# 15. Event log JSON parse errors should be logged
# ---------------------------------------------------------------------------


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
        import re
        has_silent = re.search(r"except\s+Exception\s*:\s*\n\s*pass", fn_body)
        self.assertIsNone(has_silent,
                          "load_events silently swallows JSON parse errors")


# ---------------------------------------------------------------------------
# 16. Scan log must include date, not just time
# ---------------------------------------------------------------------------


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
        # Must include %Y-%m-%d or similar date component
        has_date = "%Y-%m-%d" in fn_body or "%Y" in fn_body
        self.assertTrue(has_date,
                        "log_scan uses time-only format (%H:%M:%S) — "
                        "must include date for cross-day debugging")


if __name__ == "__main__":
    unittest.main()
