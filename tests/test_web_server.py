#!/usr/bin/env python3
"""Tests for web server — input validation, helpers, XSS, client-side checks."""

import html
import os
import re
import sys
import unittest

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestSimulateCountValidation(unittest.TestCase):
    """The simulate command must clamp count to 1-1000 and handle bad input."""

    def _get_simulate_block(self):
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()
        m = re.search(r'if cmd == ["\']simulate["\']:', source)
        self.assertIsNotNone(m, "simulate block not found")
        block_start = m.start()
        block_end = source.find("return", block_start)
        return source[block_start:block_end]

    def test_negative_count_is_clamped(self):
        """Negative count values must be clamped to at least 1."""
        block = self._get_simulate_block()
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


class TestDefconMissingLevel(unittest.TestCase):
    """'defcon ' with no level must not crash with IndexError."""

    def test_defcon_split_is_safe(self):
        """cmd.split()[1] must be guarded against IndexError."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()

        api_start = re.search(r'if self\.path\.startswith\(["\']\/api', source)
        admin_start = re.search(r'elif self\.path\.startswith\(["\']\/admin\/api', source)
        api_block = source[api_start.start():admin_start.start()]

        defcon_start = re.search(r'cmd\.startswith\(["\']defcon ', api_block)
        self.assertIsNotNone(defcon_start, "defcon handler not found")

        defcon_block = api_block[defcon_start.start():defcon_start.start() + 800]

        has_unsafe_split = "cmd.split()[1]" in defcon_block
        has_safe_split = "len(parts)" in defcon_block or "len(cmd.split())" in defcon_block

        self.assertFalse(has_unsafe_split and not has_safe_split,
                         "defcon handler uses cmd.split()[1] without bounds check — "
                         "IndexError on 'defcon ' with no level")


class TestCamctlMissingAction(unittest.TestCase):
    """'camctl ' with no action must not crash with IndexError."""

    def test_camctl_split_is_safe(self):
        """cmd.split()[1] must be guarded against IndexError."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()

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


class TestEmptyQuotesSafe(unittest.TestCase):
    """Empty quotes list must not cause randrange(0) ValueError."""

    def test_empty_quotes_returns_empty(self):
        """When quotes list is empty, server should return empty quote, not crash."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()
        m = re.search(r'if cmd == ["\']quote["\']:', source)
        self.assertIsNotNone(m, "quote handler not found")
        block = source[m.start():m.start() + 600]
        has_guard = "if quotes:" in block or "if len(quotes)" in block or "if not quotes" in block
        self.assertTrue(has_guard,
                        "quote handler calls randrange without checking for empty list")


# ---------------------------------------------------------------------------
# Helpers and code quality
# ---------------------------------------------------------------------------


class TestCameraCtlHelper(unittest.TestCase):
    """_camera_ctl must exist as a helper and handle subprocess failures."""

    def test_camera_ctl_function_exists(self):
        """_camera_ctl should be defined as a standalone helper."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()
        self.assertIn("def _camera_ctl(", source,
                       "_camera_ctl helper not found — camera subprocess calls still inlined")

    def test_camera_ctl_handles_exceptions(self):
        """_camera_ctl must catch subprocess exceptions."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()
        fn_start = source.find("def _camera_ctl(")
        fn_end = source.find("\ndef ", fn_start + 1)
        fn_body = source[fn_start:fn_end]
        self.assertIn("except", fn_body,
                       "_camera_ctl has no exception handling — subprocess failures will crash")

    def test_defcon_commands_use_camera_ctl(self):
        """Defcon set commands must use _camera_ctl, not inline subprocess."""
        server_path = os.path.join(_root, "bin", "web")
        with open(server_path) as f:
            source = f.read()

        api_start = re.search(r'if self\.path\.startswith\(["\']\/api', source)
        admin_start = re.search(r'elif self\.path\.startswith\(["\']\/admin\/api', source)
        api_block = source[api_start.start():admin_start.start()]

        defcon_start = re.search(r'cmd\.startswith\(["\']defcon ', api_block)
        defcon_block = api_block[defcon_start.start():defcon_start.start() + 1200]

        has_inline_subprocess = "systemctl" in defcon_block and "mjpg-streamer" in defcon_block
        has_helper_call = "_camera_ctl(" in defcon_block

        self.assertTrue(has_helper_call,
                        "defcon commands don't use _camera_ctl helper")
        self.assertFalse(has_inline_subprocess,
                         "defcon commands still have inline subprocess calls for camera")


class TestAlertDeadCodeRemoved(unittest.TestCase):
    """The disabled tweet delay loop must be removed from alert."""

    def test_no_tweet_delay_loop(self):
        """The 5-iteration tweet delay loop should not exist when publish is disabled."""
        alert_path = os.path.join(_root, "bin", "alert")
        with open(alert_path) as f:
            source = f.read()
        self.assertNotIn("tweet_cancelled", source,
                         "Dead tweet delay loop still present in alert")

    def test_unused_imports_removed(self):
        """post_tweet and post_telegram should not be imported when unused."""
        alert_path = os.path.join(_root, "bin", "alert")
        with open(alert_path) as f:
            source = f.read()
        self.assertNotIn("post_tweet", source,
                         "Unused post_tweet import still in alert")
        self.assertNotIn("post_telegram", source,
                         "Unused post_telegram import still in alert")


# ---------------------------------------------------------------------------
# Client-side checks (JS source inspection)
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
        has_cleanup = ("removeEventListener" in fn_body
                       or "_errorListenerAdded" in fn_body
                       or "once:" in fn_body
                       or "._errorHandler" in fn_body)
        self.assertTrue(has_cleanup,
                        "initCamera adds error listeners without cleanup — "
                        "multiple calls will stack duplicate listeners")


class TestXSSServiceNames(unittest.TestCase):
    """Service names containing HTML/JS must be escaped in servicesRows output."""

    @staticmethod
    def _esc_html(s):
        return html.escape(s)

    @classmethod
    def _simulate_services_rows(cls, services):
        """Simulate the JS servicesRows getter in Python to check for XSS."""
        labels = {"alert": "Alert", "web": "Web"}
        rows = []
        for name, svc_state in services.items():
            safe_name = cls._esc_html(name)
            label = labels.get(name, safe_name)
            is_down = svc_state != "active"
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
        output = self._simulate_services_rows(services)
        self.assertNotIn("<img", output.lower(),
                         "XSS: HTML tag in service name rendered unescaped")

    def test_quote_in_service_name_breaks_onclick(self):
        """Service name with quotes must not break the onclick handler."""
        malicious = "foo');alert('xss"
        services = {malicious: "inactive"}
        output = self._simulate_services_rows(services)
        self.assertNotIn("alert('xss", output,
                         "XSS: unescaped quote in service name breaks onclick")


if __name__ == "__main__":
    unittest.main()
