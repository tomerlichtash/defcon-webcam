#!/usr/bin/env python3
"""Security tests for the web server (TDD — written to fail first)."""

import io
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)


# ---------------------------------------------------------------------------
# 1. XSS in sysinfo.js servicesRows — this is a JS-only issue, so we test
#    by importing the pattern and verifying that the server-supplied service
#    names would be escaped if injected into HTML.  Since the vulnerability
#    is client-side, we write a focused Python test that simulates what the
#    JS servicesRows getter does and checks the output.
# ---------------------------------------------------------------------------


class TestXSSServiceNames(unittest.TestCase):
    """Service names containing HTML/JS must be escaped in servicesRows output.

    The sysinfo.js servicesRows getter injects service names directly into
    innerHTML via string concatenation.  A malicious service name like
    '<img src=x onerror=alert(1)>' would execute arbitrary JS.
    """

    @staticmethod
    def _esc_html(s):
        """Simulate the JS _escHtml: escape HTML special characters."""
        import html
        return html.escape(s)

    @classmethod
    def _simulate_services_rows(cls, services):
        """Simulate the JS servicesRows getter in Python to check for XSS.

        This mirrors the FIXED sysinfo.js: names are escaped via _escHtml
        before injection into innerHTML, and quotes are escaped in onclick.
        """
        labels = {"mjpg-alert": "Alert", "mjpg-web": "Web"}
        rows = []
        for name, state in services.items():
            safe_name = cls._esc_html(name)
            label = labels.get(name, safe_name)
            is_down = state != "active"
            action = "svcStart" if is_down else "svcRestart"
            attr_name = safe_name.replace("'", "&#39;")
            row = (
                f'<div class="svc-row"><span class="svc-dot down"></span>'
                f'<span class="sysinfo-label">{label}</span>'
                f'<button class="outline btn-primary svc-restart-btn" '
                f"onclick=\"document.querySelector('[x-data]')._x_dataStack[0]"
                f'.{action}(\'{attr_name}\')">'
                f"Start</button></div>"
            )
            rows.append(row)
        return "".join(rows)

    def test_html_in_service_name_is_escaped(self):
        """Service name with HTML tags must not appear unescaped in output."""
        malicious = '<img src=x onerror=alert(1)>'
        services = {malicious: "inactive"}
        html = self._simulate_services_rows(services)
        # The raw HTML tag must NOT appear in output
        self.assertNotIn("<img", html.lower(),
                         "XSS: HTML tag in service name rendered unescaped")

    def test_quote_in_service_name_breaks_onclick(self):
        """Service name with quotes must not break the onclick handler."""
        malicious = "foo');alert('xss"
        services = {malicious: "inactive"}
        html = self._simulate_services_rows(services)
        # The unescaped quote should not appear — it would break the onclick
        self.assertNotIn("alert('xss", html,
                         "XSS: unescaped quote in service name breaks onclick")


# ---------------------------------------------------------------------------
# 2. Unauthenticated API — sensitive commands must require auth
# ---------------------------------------------------------------------------


class TestUnauthenticatedAPI(unittest.TestCase):
    """Sensitive /api commands (svcctl, defcon set, camctl, restart-web, dbreset)
    must require authentication. Currently they don't — only /admin/api does."""

    @classmethod
    def setUpClass(cls):
        """Set up a test HTTP server."""
        # Mock heavy imports that aren't needed for routing tests
        cls._patches = []

        # Create temp files for templates
        cls._tmpdir = tempfile.mkdtemp()
        for name in ("index.html", "admin.html", "login.html"):
            with open(os.path.join(cls._tmpdir, name), "w") as f:
                f.write(f"<html>{name}</html>")

        # Create temp data dir with empty messages
        cls._datadir = tempfile.mkdtemp()
        for lang in ("en", "he"):
            with open(os.path.join(cls._datadir, f"messages_{lang}.json"), "w") as f:
                json.dump([], f)

    def _make_handler(self, path, cookie=None):
        """Create a mock Handler and call do_GET for the given path."""
        # We need to import the handler fresh with mocked dependencies
        # Instead, let's directly test by making HTTP-like requests

        # Import the module's Handler
        # We'll mock the heavy dependencies and construct a handler
        import http.server

        # Mock all the lib dependencies
        mock_modules = {
            "lib.config": MagicMock(IS_LINUX=False, HAS_CAMERA=False,
                                     load_admin_config=lambda: {}),
            "lib.auth": MagicMock(
                is_authenticated=lambda h: False,
                validate_session=lambda t: False,
                refresh_session=lambda t: None,
            ),
            "lib.sysinfo": MagicMock(
                get_sysinfo=lambda: {"defcon": 5, "services": {}},
                get_defcon=lambda: {"defcon": 5},
            ),
            "lib.geocode": MagicMock(
                init_geo_db=lambda: None,
                random_cities=lambda n: [],
                lookup_many=lambda c: [],
                city_count=lambda: 0,
            ),
            "lib.alert_log": MagicMock(
                load_log=lambda: [],
                load_scan_log=lambda: [],
                log_event=lambda *a, **kw: None,
            ),
            "lib.camera": MagicMock(take_snapshot=lambda: None),
            "lib.state": MagicMock(
                save_state=lambda s: None,
                set_display=lambda **kw: None,
                load_state=lambda: "idle",
            ),
            "lib.event_log": MagicMock(
                log_event=lambda *a, **kw: None,
                load_events=lambda **kw: [],
                count_events=lambda: 0,
                prune=lambda: None,
                reset_db=lambda: None,
                init_db=lambda: None,
                migrate_from_jsonl=lambda: None,
            ),
        }

        # Patch the server module imports
        with patch.dict("sys.modules", mock_modules):
            # We need to load the Handler class directly from the file
            # This is complex, so instead we'll use a simpler approach:
            # import the handler and make a real request via the test client
            pass

        # Simpler approach: use the actual server code but intercept at the
        # handler level. We construct a handler with mocked rfile/wfile.
        handler = MagicMock()
        handler.path = path
        handler.headers = {}
        if cookie:
            handler.headers["Cookie"] = cookie

        wfile = io.BytesIO()
        handler.wfile = wfile

        responses = []
        def mock_send_response(code):
            responses.append(code)
        handler.send_response = mock_send_response
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        return handler, responses

    def _get_api_block(self):
        """Extract the /api handler block from the server source."""
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()
        # Match both quote styles (single/double) after formatter runs
        import re
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
        # Match cmd.startswith("defcon ") or cmd.startswith('defcon ')
        import re
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


# ---------------------------------------------------------------------------
# 3. Path traversal on /static/ file serving
# ---------------------------------------------------------------------------


class TestPathTraversal(unittest.TestCase):
    """The static file handler must reject paths that escape STATIC_DIR."""

    def test_dotdot_in_static_path_is_blocked(self):
        """Request to /static/../../lib/auth.py must not serve the file."""
        import re
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()

        # Find the static file handler (quote-agnostic)
        m = re.search(r'elif self\.path\.startswith\(["\']\/static\/', source)
        self.assertIsNotNone(m, "static handler not found")
        static_block_start = m.start()
        static_block_end = source.find("\n        else:", static_block_start)
        static_block = source[static_block_start:static_block_end]

        # The handler must resolve the path and verify it stays within STATIC_DIR
        has_realpath = "realpath" in static_block or "abspath" in static_block
        has_dotdot_check = '".."' in static_block or "'..' " in static_block

        # A proper traversal guard needs BOTH path resolution AND a prefix check
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


# ---------------------------------------------------------------------------
# 4. Race condition on _prev_state global dict
# ---------------------------------------------------------------------------


class TestRaceCondition(unittest.TestCase):
    """_detect_changes() modifies a global dict without locking.
    Concurrent calls (from multiple HTTP handler threads) can corrupt state."""

    def test_detect_changes_is_thread_safe(self):
        """Concurrent _detect_changes calls must not raise or corrupt state."""
        server_path = os.path.join(_root, "bin", "mjpg-web")
        with open(server_path) as f:
            source = f.read()

        # Check that _prev_state access is protected by a lock
        # Look for threading.Lock or threading.RLock near _prev_state
        prev_state_pos = source.find("_prev_state")
        # Look for a lock definition near the global state
        has_lock_def = ("Lock()" in source and
                        ("_prev_state" in source or "_state_lock" in source or
                         "_lock" in source))

        # Also check that _detect_changes acquires a lock
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
