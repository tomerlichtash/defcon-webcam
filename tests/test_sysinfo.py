#!/usr/bin/env python3
"""Tests for sysinfo module — helpers and data extraction."""

import os
import sys
import unittest
from unittest.mock import patch

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)


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
        _mock_lookup.assert_called_once_with(["single city"])


if __name__ == "__main__":
    unittest.main()
