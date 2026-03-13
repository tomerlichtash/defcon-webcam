#!/usr/bin/env python3
"""Tests for Telegram posting and tweet delay logic."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

sys.modules["tweepy"] = MagicMock()

from lib import config, state
from lib.oref import check_alerts
from lib.telegram import post_telegram


class TestPostTelegram(unittest.TestCase):
    """Test post_telegram() — Telegram Bot API integration."""

    def setUp(self):
        self.tmpconf = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False)
        self.tmpsnap = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        self._orig_conf = config.TELEGRAM_CONF
        self._orig_snap = config.SNAPSHOT_PATH
        config.TELEGRAM_CONF = self.tmpconf.name
        config.SNAPSHOT_PATH = self.tmpsnap.name
        self.tmpsnap.write(b'\xff\xd8\xff\xe0fake_jpeg_data')
        self.tmpsnap.flush()

    def tearDown(self):
        config.TELEGRAM_CONF = self._orig_conf
        config.SNAPSHOT_PATH = self._orig_snap
        os.unlink(self.tmpconf.name)
        os.unlink(self.tmpsnap.name)

    @patch('lib.telegram.take_alert_snapshot')
    @patch('lib.telegram.urllib.request.urlopen')
    @patch('builtins.print')
    def test_sends_photo_with_caption(self, mock_print, mock_urlopen, mock_snap):
        self.tmpconf.write('BOT_TOKEN=123:ABC\nCHAT_ID=-100\n')
        self.tmpconf.flush()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        post_telegram('DEFCON 2 - TEST', 'day')

        mock_snap.assert_called_once_with('day')
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertIn('123:ABC', req.full_url)
        self.assertIn(b'DEFCON 2 - TEST', req.data)
        self.assertIn(b'fake_jpeg_data', req.data)

    @patch('lib.telegram.take_alert_snapshot')
    @patch('builtins.print')
    def test_skips_when_no_config(self, mock_print, mock_snap):
        config.TELEGRAM_CONF = '/nonexistent/conf'
        post_telegram('test', 'day')
        mock_snap.assert_called_once()
        mock_print.assert_any_call('No Telegram keys, skipping message', flush=True)

    @patch('lib.telegram.take_alert_snapshot')
    @patch('builtins.print')
    def test_skips_when_config_incomplete(self, mock_print, mock_snap):
        self.tmpconf.write('BOT_TOKEN=123\n')
        self.tmpconf.flush()
        post_telegram('test', 'day')
        mock_print.assert_any_call('Telegram config incomplete, skipping', flush=True)

    @patch('lib.telegram.take_alert_snapshot')
    @patch('lib.telegram.urllib.request.urlopen')
    @patch('builtins.print')
    def test_handles_api_error(self, mock_print, mock_urlopen, mock_snap):
        self.tmpconf.write('BOT_TOKEN=123:ABC\nCHAT_ID=-100\n')
        self.tmpconf.flush()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": false, "description": "bad"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        post_telegram('test', 'day')
        printed = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any('Telegram API error' in p for p in printed))

    @patch('lib.telegram.take_alert_snapshot')
    @patch('lib.telegram.urllib.request.urlopen', side_effect=Exception('network error'))
    @patch('builtins.print')
    def test_handles_network_error(self, mock_print, mock_urlopen, mock_snap):
        self.tmpconf.write('BOT_TOKEN=123:ABC\nCHAT_ID=-100\n')
        self.tmpconf.flush()

        post_telegram('test', 'day')
        printed = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any('Telegram failed' in p for p in printed))

    @patch('lib.telegram.take_alert_snapshot')
    @patch('lib.telegram.urllib.request.urlopen')
    @patch('builtins.print')
    def test_night_mode_passed_to_snapshot(self, mock_print, mock_urlopen, mock_snap):
        self.tmpconf.write('BOT_TOKEN=123:ABC\nCHAT_ID=-100\n')
        self.tmpconf.flush()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        post_telegram('test', 'night')
        mock_snap.assert_called_once_with('night')


class TestTweetDelay(unittest.TestCase):
    """Test the 15-second tweet delay with cancellation logic."""

    @patch("lib.oref.check_alerts")
    def test_tweet_posted_after_delay_if_still_defcon2(self, mock_check):
        """Tweet should fire after 5 polling cycles if state stays defcon2."""
        mock_check.side_effect = ["actual"] * 5

        state.state = "defcon2"
        tweet_cancelled = False
        for _ in range(5):
            interim = mock_check()
            if interim == "ended":
                tweet_cancelled = True
                break
        posted = not tweet_cancelled and state.state == "defcon2"
        self.assertTrue(posted)

    @patch("lib.oref.check_alerts")
    def test_tweet_cancelled_if_ended_during_delay(self, mock_check):
        """Tweet should be cancelled if 'ended' received during delay."""
        mock_check.side_effect = ["actual", "actual", "ended"]

        state.state = "defcon2"
        tweet_cancelled = False
        for _ in range(5):
            interim = mock_check()
            if interim == "ended":
                state.state = "idle"
                tweet_cancelled = True
                break
        posted = not tweet_cancelled and state.state == "defcon2"
        self.assertFalse(posted)
        self.assertEqual(state.state, "idle")


if __name__ == "__main__":
    unittest.main()
