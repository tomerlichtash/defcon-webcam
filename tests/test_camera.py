#!/usr/bin/env python3
"""Tests for camera snapshot functions — mocked subprocess calls."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

from lib.camera import take_snapshot, take_alert_snapshot


class TestTakeSnapshot(unittest.TestCase):
    """Test take_snapshot with mocked subprocess."""

    @patch("lib.camera.config.HAS_CAMERA", True)
    @patch("subprocess.run")
    def test_calls_curl(self, mock_run):
        take_snapshot()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "curl")
        self.assertIn("http://localhost:8080/?action=snapshot", args)

    @patch("lib.camera.config.HAS_CAMERA", False)
    @patch("subprocess.run")
    @patch("builtins.print")
    def test_skips_without_camera(self, mock_print, mock_run):
        take_snapshot()
        mock_run.assert_not_called()
        mock_print.assert_called_once()
        self.assertIn("No camera", mock_print.call_args[0][0])


class TestTakeAlertSnapshot(unittest.TestCase):
    """Test take_alert_snapshot with mode handling."""

    @patch("lib.camera.config.HAS_CAMERA", True)
    @patch("lib.camera.time.sleep")
    @patch("subprocess.run")
    def test_day_mode_no_exposure(self, mock_run, mock_sleep):
        """Day mode should just take a snapshot, no v4l2-ctl."""
        take_alert_snapshot("day")
        # Should call curl once, no v4l2-ctl
        self.assertEqual(mock_run.call_count, 1)
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "curl")
        mock_sleep.assert_not_called()

    @patch("lib.camera.config.HAS_CAMERA", True)
    @patch("lib.camera.time.sleep")
    @patch("subprocess.run")
    def test_night_mode_adjusts_exposure(self, mock_run, mock_sleep):
        """Night mode should set exposure before and restore after."""
        take_alert_snapshot("night")
        # v4l2-ctl set, curl snapshot, v4l2-ctl restore = 3 calls
        self.assertEqual(mock_run.call_count, 3)
        # First call should be v4l2-ctl (exposure set)
        first_args = mock_run.call_args_list[0][0][0]
        self.assertEqual(first_args[0], "v4l2-ctl")
        self.assertIn("auto_exposure=1", " ".join(first_args))
        # Second call should be curl (snapshot)
        second_args = mock_run.call_args_list[1][0][0]
        self.assertEqual(second_args[0], "curl")
        # Third call should be v4l2-ctl (restore)
        third_args = mock_run.call_args_list[2][0][0]
        self.assertEqual(third_args[0], "v4l2-ctl")
        self.assertIn("auto_exposure=3", " ".join(third_args))
        # Should sleep between set and snapshot
        mock_sleep.assert_called_once_with(3)

    @patch("lib.camera.config.HAS_CAMERA", False)
    @patch("subprocess.run")
    @patch("builtins.print")
    def test_no_camera_skips(self, mock_print, mock_run):
        take_alert_snapshot("day")
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
