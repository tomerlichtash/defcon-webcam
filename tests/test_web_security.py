#!/usr/bin/env python3
"""Security tests — authentication, path traversal, thread safety."""

import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)


class TestUnauthenticatedAPI(unittest.TestCase):
    """Sensitive /api commands (svcctl, defcon set, camctl, restart-web, dbreset)
    must require authentication."""

    def _get_api_block(self):
        """Extract the /api handler block from the server source."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()
        api_start = re.search(r'if self\.path\.startswith\(["\']\/api', source)
        admin_start = re.search(r'elif self\.path\.startswith\(["\']\/admin\/api', source)
        self.assertIsNotNone(api_start, "/api block not found")
        self.assertIsNotNone(admin_start, "/admin/api block not found")
        return source[api_start.start():admin_start.start()]

    def test_svcctl_requires_auth(self):
        """/api?cmd=svcctl without auth should be rejected."""
        api_block = self._get_api_block()
        svcctl_pos = api_block.find("svcctl")
        self.assertGreater(svcctl_pos, 0, "svcctl not found in /api block")
        auth_before = api_block[:svcctl_pos].find("is_authenticated")
        self.assertGreater(auth_before, 0,
                           "SECURITY: /api svcctl has no authentication check — "
                           "anyone can restart services without login")

    def test_defcon_set_requires_auth(self):
        """/api?cmd=defcon+2 without auth should be rejected."""
        api_block = self._get_api_block()
        m = re.search(r'cmd\.startswith\(["\']defcon ', api_block)
        self.assertIsNotNone(m, "defcon set not found in /api block")
        auth_before = api_block[:m.start()].find("is_authenticated")
        self.assertGreater(auth_before, 0,
                           "SECURITY: /api defcon set has no authentication check — "
                           "anyone can change DEFCON level without login")

    def test_restart_web_requires_auth(self):
        """/api?cmd=restart-web without auth should be rejected."""
        api_block = self._get_api_block()
        restart_pos = api_block.find("restart-web")
        self.assertGreater(restart_pos, 0, "restart-web not found in /api block")
        auth_before = api_block[:restart_pos].find("is_authenticated")
        self.assertGreater(auth_before, 0,
                           "SECURITY: /api restart-web has no authentication check — "
                           "anyone can restart the web server without login")

    def test_dbreset_requires_auth(self):
        """/api?cmd=dbreset without auth should be rejected."""
        api_block = self._get_api_block()
        dbreset_pos = api_block.find("dbreset")
        self.assertGreater(dbreset_pos, 0, "dbreset not found in /api block")
        auth_before = api_block[:dbreset_pos].find("is_authenticated")
        self.assertGreater(auth_before, 0,
                           "SECURITY: /api dbreset has no authentication check — "
                           "anyone can wipe the event log without login")


class TestPathTraversal(unittest.TestCase):
    """The static file handler must reject paths that escape STATIC_DIR."""

    def test_dotdot_in_static_path_is_blocked(self):
        """Request to /static/../../lib/auth.py must not serve the file."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()

        m = re.search(r'elif self\.path\.startswith\(["\']\/static\/', source)
        self.assertIsNotNone(m, "static handler not found")
        static_block_start = m.start()
        static_block_end = source.find("\n        else:", static_block_start)
        static_block = source[static_block_start:static_block_end]

        has_realpath = "realpath" in static_block or "abspath" in static_block
        has_dotdot_check = '".."' in static_block or "'..' " in static_block

        has_prefix_guard = False
        if has_realpath:
            for line in static_block.split("\n"):
                if "startswith" in line and "STATIC_DIR" in line:
                    has_prefix_guard = True
                    break

        self.assertTrue(
            (has_realpath and has_prefix_guard) or has_dotdot_check,
            "SECURITY: Static file handler has no path traversal protection — "
            "/static/../../etc/passwd would serve arbitrary files"
        )


class TestRaceCondition(unittest.TestCase):
    """_detect_changes() modifies a global dict without locking.
    Concurrent calls (from multiple HTTP handler threads) can corrupt state."""

    def test_detect_changes_is_thread_safe(self):
        """Concurrent _detect_changes calls must not raise or corrupt state."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()

        has_lock_def = ("Lock()" in source and
                        ("_prev_state" in source or "_state_lock" in source or
                         "_lock" in source))

        detect_fn_start = source.find("def _detect_changes")
        detect_fn_end = source.find("\ndef ", detect_fn_start + 1)
        detect_fn = source[detect_fn_start:detect_fn_end]

        has_lock_usage = ("acquire" in detect_fn or
                          "with " in detect_fn and "lock" in detect_fn.lower())

        self.assertTrue(
            has_lock_def and has_lock_usage,
            "SECURITY: _detect_changes() modifies global _prev_state without "
            "a threading lock — concurrent requests can corrupt state"
        )


if __name__ == "__main__":
    unittest.main()
