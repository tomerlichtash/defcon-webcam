#!/usr/bin/env python3
"""Tests for sysinfo gathering — formatting, service checks, get_sysinfo, get_defcon."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

from lib.sysinfo import _human_size, _uptime_pretty, get_sysinfo, get_defcon


class TestHumanSize(unittest.TestCase):
    """Test _human_size byte formatting."""

    def test_bytes(self):
        self.assertEqual(_human_size(0), "0 B")
        self.assertEqual(_human_size(512), "512 B")

    def test_kilobytes(self):
        self.assertEqual(_human_size(1024), "1.0 KB")
        self.assertEqual(_human_size(2048), "2.0 KB")

    def test_megabytes(self):
        result = _human_size(5 * 1024 * 1024)
        self.assertIn("5.0", result)
        self.assertIn("MB", result)

    def test_gigabytes(self):
        result = _human_size(3 * 1024 * 1024 * 1024)
        self.assertIn("3.0", result)
        self.assertIn("GB", result)

    def test_terabytes(self):
        result = _human_size(2 * 1024 ** 4)
        self.assertIn("TB", result)


class TestUptimePretty(unittest.TestCase):
    """Test _uptime_pretty formatting (mocked system calls)."""

    @patch("lib.sysinfo.IS_LINUX", False)
    @patch("subprocess.run")
    def test_mac_uptime(self, mock_run):
        import time
        boot_time = int(time.time()) - 3661  # 1 hour, 1 minute, 1 second ago
        mock_run.return_value = MagicMock(
            stdout=f"{{ sec = {boot_time}, usec = 0 }} Thu Jan  1 00:00:00 2025"
        )
        result = _uptime_pretty()
        self.assertIn("1 hour", result)
        self.assertIn("1 minute", result)

    @patch("lib.sysinfo.IS_LINUX", False)
    @patch("subprocess.run", side_effect=Exception("fail"))
    def test_mac_uptime_error(self, mock_run):
        self.assertEqual(_uptime_pretty(), "unknown")

    @patch("lib.sysinfo.IS_LINUX", False)
    @patch("subprocess.run")
    def test_mac_uptime_no_match(self, mock_run):
        mock_run.return_value = MagicMock(stdout="garbage output")
        self.assertEqual(_uptime_pretty(), "unknown")

    @patch("lib.sysinfo.IS_LINUX", True)
    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_linux_uptime_missing_proc(self, mock_open):
        self.assertEqual(_uptime_pretty(), "unknown")


class TestGetSysinfo(unittest.TestCase):
    """Test get_sysinfo with mocked dependencies."""

    @patch("lib.sysinfo.load_state", return_value="idle")
    @patch("lib.sysinfo.city_count", return_value=150)
    @patch("lib.sysinfo.HAS_CAMERA", False)
    @patch("lib.sysinfo.IS_LINUX", False)
    @patch("os.path.getsize", return_value=4096)
    @patch("lib.sysinfo._uptime_pretty", return_value="5 hours")
    @patch("lib.sysinfo._service_state_mac", return_value="active")
    def test_basic_sysinfo(self, mock_svc, mock_uptime, mock_size, *_):
        info = get_sysinfo()
        self.assertEqual(info["defcon"], 5)
        self.assertEqual(info["uptime"], "5 hours")
        self.assertIn("services", info)
        self.assertFalse(info["has_camera"])
        self.assertTrue(info["db_ok"])

    @patch("lib.sysinfo.load_state", return_value="defcon2")
    @patch("lib.sysinfo._alert_cities", return_value=[{"name": "Tel Aviv", "lat": 32.08, "lng": 34.78}])
    @patch("lib.sysinfo.city_count", return_value=100)
    @patch("lib.sysinfo.HAS_CAMERA", False)
    @patch("lib.sysinfo.IS_LINUX", False)
    @patch("os.path.getsize", return_value=4096)
    @patch("lib.sysinfo._uptime_pretty", return_value="1 hour")
    @patch("lib.sysinfo._service_state_mac", return_value="active")
    def test_sysinfo_defcon2_includes_cities(self, *_):
        info = get_sysinfo()
        self.assertEqual(info["defcon"], 2)
        self.assertIn("alert_cities", info)
        self.assertEqual(len(info["alert_cities"]), 1)

    @patch("lib.sysinfo.load_state", return_value="idle")
    @patch("lib.sysinfo.city_count", side_effect=Exception("db error"))
    @patch("lib.sysinfo.HAS_CAMERA", False)
    @patch("lib.sysinfo.IS_LINUX", False)
    @patch("os.path.getsize", side_effect=FileNotFoundError)
    @patch("lib.sysinfo._uptime_pretty", return_value="1 hour")
    @patch("lib.sysinfo._service_state_mac", return_value="inactive")
    def test_sysinfo_missing_dbs(self, *_):
        info = get_sysinfo()
        self.assertFalse(info["db_ok"])
        self.assertFalse(info["geo_ok"])
        self.assertEqual(info["geo_count"], 0)

    @patch("lib.sysinfo.load_state", return_value="idle")
    @patch("lib.sysinfo.city_count", return_value=0)
    @patch("lib.sysinfo.HAS_CAMERA", False)
    @patch("lib.sysinfo.IS_LINUX", False)
    @patch("os.path.getsize", return_value=0)
    @patch("lib.sysinfo._uptime_pretty", return_value="1 minute")
    @patch("lib.sysinfo._service_state_mac", return_value="active")
    def test_load_average(self, *_):
        """Load average should be computed on macOS."""
        info = get_sysinfo()
        self.assertIn("load", info)
        self.assertTrue(info["load"].endswith("%"))


class TestGetDefcon(unittest.TestCase):
    """Test get_defcon lightweight endpoint."""

    @patch("lib.sysinfo.load_state", return_value="idle")
    def test_idle(self, _):
        result = get_defcon()
        self.assertEqual(result["defcon"], 5)
        self.assertNotIn("alert_cities", result)

    @patch("lib.sysinfo._alert_cities", return_value=[{"name": "Haifa"}])
    @patch("lib.sysinfo.load_state", return_value="defcon2")
    def test_defcon2_with_cities(self, *_):
        result = get_defcon()
        self.assertEqual(result["defcon"], 2)
        self.assertIn("alert_cities", result)

    @patch("lib.sysinfo._alert_cities", return_value=None)
    @patch("lib.sysinfo.load_state", return_value="defcon4")
    def test_defcon4_no_cities(self, *_):
        result = get_defcon()
        self.assertEqual(result["defcon"], 4)
        self.assertNotIn("alert_cities", result)


class TestServiceStateMac(unittest.TestCase):
    """Test _service_state_mac with mocked pgrep."""

    @patch("subprocess.run")
    def test_active(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from lib.sysinfo import _service_state_mac
        self.assertEqual(_service_state_mac("mjpg-alert"), "active")

    @patch("subprocess.run")
    def test_inactive(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        from lib.sysinfo import _service_state_mac
        self.assertEqual(_service_state_mac("mjpg-alert"), "inactive")

    @patch("subprocess.run", side_effect=Exception("pgrep not found"))
    def test_error(self, _):
        from lib.sysinfo import _service_state_mac
        self.assertEqual(_service_state_mac("mjpg-alert"), "unknown")


if __name__ == "__main__":
    unittest.main()
