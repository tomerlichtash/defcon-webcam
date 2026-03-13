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
    """Camera component must clean up stream watchers in disconnectedCallback."""

    def test_disconnected_callback_clears_watchdog(self):
        """camera-content component must clear watchdog on disconnect."""
        cam_path = os.path.join(_root, "static", "js", "components", "camera-content.js")
        with open(cam_path) as f:
            source = f.read()
        self.assertIn("disconnectedCallback", source,
                       "camera-content has no disconnectedCallback — "
                       "stream watchdog will leak on component removal")
        self.assertIn("clearInterval", source,
                       "camera-content disconnectedCallback does not clear watchdog")


class TestXSSServiceNames(unittest.TestCase):
    """Lit templates use tagged template literals which auto-escape by default.
    This test verifies the sysinfo component uses Lit html`` templates,
    not innerHTML, for rendering service rows."""

    def test_service_rows_use_lit_templates(self):
        """sysinfo-content must render service rows with Lit html`` templates,
        not innerHTML with string concatenation."""
        sysinfo_path = os.path.join(_root, "static", "js", "components", "sysinfo-content.js")
        with open(sysinfo_path) as f:
            source = f.read()
        # Find the _renderServiceRows method
        fn_start = source.find("_renderServiceRows")
        self.assertNotEqual(fn_start, -1,
                            "sysinfo-content must have _renderServiceRows method")
        fn_body = source[fn_start:fn_start + 800]
        # Must use Lit html`` template, not string concatenation
        self.assertIn("html`", fn_body,
                       "service rows must use Lit html`` tagged template for XSS safety")
        # Must not use onclick string handlers (old Alpine pattern)
        self.assertNotIn("onclick=", fn_body,
                         "service rows must not use onclick string handlers")


if __name__ == "__main__":
    unittest.main()
