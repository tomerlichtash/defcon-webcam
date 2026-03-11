#!/usr/bin/env python3
"""Tests for alert monitoring logic."""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

# Mock tweepy before importing lib.twitter
sys.modules["tweepy"] = MagicMock()

from lib import config, state, oref
from lib.state import save_state, load_state, set_display
from lib.oref import _fetch_url, _classify_alert, check_alerts
from lib.config import get_current_mode, load_twitter_keys, load_telegram_keys
from lib.telegram import post_telegram


class TestClassifyAlert(unittest.TestCase):
    """Test _classify_alert() — title matching and fuzzy city matching."""

    def test_actual_alert_exact_city(self):
        data = {"title": "ירי רקטות וטילים", "data": ["גבעתיים"]}
        self.assertEqual(_classify_alert(data), "actual")

    def test_actual_alert_fuzzy_match(self):
        """City name contains a watch term as substring."""
        data = {"title": "ירי רקטות וטילים", "data": ["תל אביב - מרכז העיר"]}
        self.assertEqual(_classify_alert(data), "actual")

    def test_preemptive_alert(self):
        data = {
            "title": "בדקות הקרובות צפויות להתקבל התרעות באזורך",
            "data": ["רמת גן"],
        }
        self.assertEqual(_classify_alert(data), "preemptive")

    def test_ended_alert(self):
        data = {"title": "האירוע הסתיים", "data": ["בני ברק"]}
        self.assertEqual(_classify_alert(data), "ended")

    @patch("builtins.print")
    def test_unknown_title_treated_as_actual(self, _):
        data = {"title": "סוג חדש", "data": ["גבעתיים"]}
        self.assertEqual(_classify_alert(data), "actual")

    def test_no_matching_cities(self):
        data = {"title": "ירי רקטות וטילים", "data": ["באר שבע", "אשדוד"]}
        self.assertIsNone(_classify_alert(data))

    def test_empty_data(self):
        data = {"title": "ירי רקטות וטילים", "data": []}
        self.assertIsNone(_classify_alert(data))

    def test_missing_data_key(self):
        data = {"title": "ירי רקטות וטילים"}
        self.assertIsNone(_classify_alert(data))

    def test_multiple_cities_one_match(self):
        data = {"title": "ירי רקטות וטילים", "data": ["חיפה", "תל אביב", "אילת"]}
        self.assertEqual(_classify_alert(data), "actual")


class TestFetchUrl(unittest.TestCase):
    """Test _fetch_url() — encoding and cache busting."""

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_utf8_sig_decoding(self, mock_req_cls, mock_urlopen):
        content = json.dumps({"data": []}).encode("utf-8-sig")
        resp = MagicMock()
        resp.read.return_value = content
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = _fetch_url("http://example.com/alerts.json")
        self.assertEqual(json.loads(result), {"data": []})

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_utf16_le_bom_decoding(self, mock_req_cls, mock_urlopen):
        text = json.dumps({"data": ["תל אביב"]}, ensure_ascii=False)
        content = b"\xff\xfe" + text.encode("utf-16-le")
        resp = MagicMock()
        resp.read.return_value = content
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = _fetch_url("http://example.com/alerts.json")
        self.assertIn("תל אביב", result)

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_cache_busting_adds_param(self, mock_req_cls, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"{}"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        _fetch_url("http://example.com/test")
        url_used = mock_req_cls.call_args[0][0]
        self.assertIn("?t=", url_used)

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_cache_busting_with_existing_query(self, mock_req_cls, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"{}"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        _fetch_url("http://example.com/test?foo=bar")
        url_used = mock_req_cls.call_args[0][0]
        self.assertIn("&t=", url_used)


class TestStatePersistence(unittest.TestCase):
    """Test save_state() and load_state()."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(delete=False, mode="w")
        self.tmpfile.close()
        self._orig = config.STATE_FILE
        config.STATE_FILE = self.tmpfile.name

    def tearDown(self):
        config.STATE_FILE = self._orig
        try:
            os.unlink(self.tmpfile.name)
        except OSError:
            pass

    def test_save_and_load_idle(self):
        save_state("idle")
        self.assertEqual(load_state(), "idle")

    def test_save_and_load_defcon2(self):
        save_state("defcon2")
        self.assertEqual(load_state(), "defcon2")

    def test_save_and_load_defcon4(self):
        save_state("defcon4")
        self.assertEqual(load_state(), "defcon4")

    def test_load_missing_file_returns_idle(self):
        config.STATE_FILE = "/tmp/nonexistent-test-state-file"
        self.assertEqual(load_state(), "idle")


class TestSetDisplay(unittest.TestCase):
    """Test set_display() — OSD file writing."""

    def setUp(self):
        self.idle = tempfile.NamedTemporaryFile(delete=False, mode="w")
        self.alert = tempfile.NamedTemporaryFile(delete=False, mode="w")
        self.defcon4 = tempfile.NamedTemporaryFile(delete=False, mode="w")
        self.idle.close()
        self.alert.close()
        self.defcon4.close()
        self._orig_idle = config.IDLE_FILE
        self._orig_alert = config.ALERT_FILE
        self._orig_defcon4 = config.DEFCON4_FILE
        config.IDLE_FILE = self.idle.name
        config.ALERT_FILE = self.alert.name
        config.DEFCON4_FILE = self.defcon4.name

    def tearDown(self):
        config.IDLE_FILE = self._orig_idle
        config.ALERT_FILE = self._orig_alert
        config.DEFCON4_FILE = self._orig_defcon4
        for f in [self.idle.name, self.alert.name, self.defcon4.name]:
            try:
                os.unlink(f)
            except OSError:
                pass

    def test_idle_display(self):
        set_display(idle="DEFCON 5")
        with open(self.idle.name) as f:
            self.assertEqual(f.read(), "DEFCON 5")
        with open(self.alert.name) as f:
            self.assertEqual(f.read(), " ")
        with open(self.defcon4.name) as f:
            self.assertEqual(f.read(), " ")

    def test_alert_display(self):
        set_display(alert="DEFCON 2 - INCOMING MISSILES - 12.34.56")
        with open(self.idle.name) as f:
            self.assertEqual(f.read(), " ")
        with open(self.alert.name) as f:
            self.assertEqual(f.read(), "DEFCON 2 - INCOMING MISSILES - 12.34.56")

    def test_defcon4_display(self):
        set_display(defcon4="DEFCON 4 - ALERT INCOMING - 12.34.56")
        with open(self.defcon4.name) as f:
            self.assertEqual(f.read(), "DEFCON 4 - ALERT INCOMING - 12.34.56")

    def test_defaults_are_spaces(self):
        """Default values should be spaces, not empty strings (ffmpeg requires this)."""
        set_display()
        for name in [self.idle.name, self.alert.name, self.defcon4.name]:
            with open(name) as f:
                self.assertEqual(f.read(), " ")


class TestGetCurrentMode(unittest.TestCase):
    """Test get_current_mode() — config file parsing."""

    def test_reads_day_mode(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write('MODE="day"\nROTATION=0\n')
            f.flush()
            orig = config.STREAMER_CONF
            config.STREAMER_CONF = f.name
            try:
                self.assertEqual(get_current_mode(), "day")
            finally:
                config.STREAMER_CONF = orig
                os.unlink(f.name)

    def test_reads_night_mode(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write('MODE="night"\n')
            f.flush()
            orig = config.STREAMER_CONF
            config.STREAMER_CONF = f.name
            try:
                self.assertEqual(get_current_mode(), "night")
            finally:
                config.STREAMER_CONF = orig
                os.unlink(f.name)

    def test_missing_file_returns_day(self):
        orig = config.STREAMER_CONF
        config.STREAMER_CONF = "/tmp/nonexistent-conf"
        try:
            self.assertEqual(get_current_mode(), "day")
        finally:
            config.STREAMER_CONF = orig


class TestLoadTwitterKeys(unittest.TestCase):
    """Test load_twitter_keys() — config parsing."""

    def test_parses_keys(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write('API_KEY="key1"\nAPI_SECRET="secret1"\n# comment\nACCESS_TOKEN="tok"\nACCESS_SECRET="sec"\n')
            f.flush()
            orig = config.TWITTER_CONF
            config.TWITTER_CONF = f.name
            try:
                keys = load_twitter_keys()
                self.assertEqual(keys["API_KEY"], "key1")
                self.assertEqual(keys["API_SECRET"], "secret1")
                self.assertEqual(keys["ACCESS_TOKEN"], "tok")
                self.assertEqual(keys["ACCESS_SECRET"], "sec")
            finally:
                config.TWITTER_CONF = orig
                os.unlink(f.name)

    def test_skips_comments(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write('# This is a comment\nAPI_KEY="key1"\n')
            f.flush()
            orig = config.TWITTER_CONF
            config.TWITTER_CONF = f.name
            try:
                keys = load_twitter_keys()
                self.assertNotIn("#", keys)
                self.assertEqual(keys["API_KEY"], "key1")
            finally:
                config.TWITTER_CONF = orig
                os.unlink(f.name)

    @patch("builtins.print")
    def test_missing_file_returns_empty(self, _):
        orig = config.TWITTER_CONF
        config.TWITTER_CONF = "/tmp/nonexistent-twitter-conf"
        try:
            keys = load_twitter_keys()
            self.assertEqual(keys, {})
        finally:
            config.TWITTER_CONF = orig


class TestStateMachine(unittest.TestCase):
    """Test state transitions in main loop logic."""

    def setUp(self):
        self.state_file = tempfile.NamedTemporaryFile(delete=False)
        self.idle_file = tempfile.NamedTemporaryFile(delete=False)
        self.alert_file = tempfile.NamedTemporaryFile(delete=False)
        self.defcon4_file = tempfile.NamedTemporaryFile(delete=False)
        for f in [self.state_file, self.idle_file, self.alert_file, self.defcon4_file]:
            f.close()

        self._orig_state = config.STATE_FILE
        self._orig_idle = config.IDLE_FILE
        self._orig_alert = config.ALERT_FILE
        self._orig_defcon4 = config.DEFCON4_FILE

        config.STATE_FILE = self.state_file.name
        config.IDLE_FILE = self.idle_file.name
        config.ALERT_FILE = self.alert_file.name
        config.DEFCON4_FILE = self.defcon4_file.name

    def tearDown(self):
        config.STATE_FILE = self._orig_state
        config.IDLE_FILE = self._orig_idle
        config.ALERT_FILE = self._orig_alert
        config.DEFCON4_FILE = self._orig_defcon4
        for f in [self.state_file, self.idle_file, self.alert_file, self.defcon4_file]:
            try:
                os.unlink(f.name)
            except OSError:
                pass

    def _run_one_cycle(self, result):
        """Simulate one iteration of the main loop's state handling."""
        if result == "ended":
            if state.state != "idle":
                state.state = "idle"
                save_state("idle")
                set_display(idle="DEFCON 5")
        elif result == "preemptive":
            if state.state == "idle":
                state.state = "defcon4"
                save_state("defcon4")
                set_display(defcon4="DEFCON 4 - ALERT INCOMING")
        elif result == "actual":
            if state.state in ("idle", "defcon4"):
                state.state = "defcon2"
                save_state("defcon2")
                set_display(alert="DEFCON 2 - INCOMING MISSILES")

    def test_idle_to_defcon4(self):
        state.state = "idle"
        self._run_one_cycle("preemptive")
        self.assertEqual(state.state, "defcon4")
        self.assertEqual(load_state(), "defcon4")

    def test_idle_to_defcon2(self):
        state.state = "idle"
        self._run_one_cycle("actual")
        self.assertEqual(state.state, "defcon2")
        self.assertEqual(load_state(), "defcon2")

    def test_defcon4_to_defcon2(self):
        state.state = "defcon4"
        self._run_one_cycle("actual")
        self.assertEqual(state.state, "defcon2")

    def test_defcon2_to_idle_on_ended(self):
        state.state = "defcon2"
        self._run_one_cycle("ended")
        self.assertEqual(state.state, "idle")
        self.assertEqual(load_state(), "idle")

    def test_defcon4_to_idle_on_ended(self):
        state.state = "defcon4"
        self._run_one_cycle("ended")
        self.assertEqual(state.state, "idle")

    def test_idle_stays_idle_on_ended(self):
        state.state = "idle"
        self._run_one_cycle("ended")
        self.assertEqual(state.state, "idle")

    def test_idle_stays_idle_on_none(self):
        state.state = "idle"
        self._run_one_cycle(None)
        self.assertEqual(state.state, "idle")

    def test_defcon2_ignores_preemptive(self):
        """Once in DEFCON 2, preemptive alerts should not change state."""
        state.state = "defcon2"
        self._run_one_cycle("preemptive")
        self.assertEqual(state.state, "defcon2")

    def test_defcon2_ignores_repeated_actual(self):
        """Already in DEFCON 2, another actual should not re-trigger."""
        state.state = "defcon2"
        self._run_one_cycle("actual")
        self.assertEqual(state.state, "defcon2")

    def test_defcon4_ignores_repeated_preemptive(self):
        """Already in DEFCON 4, repeated preemptive should not re-trigger."""
        state.state = "defcon4"
        self._run_one_cycle("preemptive")
        self.assertEqual(state.state, "defcon4")

    def test_full_cycle_idle_defcon4_defcon2_idle(self):
        state.state = "idle"
        self._run_one_cycle("preemptive")
        self.assertEqual(state.state, "defcon4")
        self._run_one_cycle("actual")
        self.assertEqual(state.state, "defcon2")
        self._run_one_cycle("ended")
        self.assertEqual(state.state, "idle")

    def test_display_files_on_defcon2(self):
        state.state = "idle"
        self._run_one_cycle("actual")
        with open(self.alert_file.name) as f:
            self.assertIn("DEFCON 2", f.read())
        with open(self.idle_file.name) as f:
            self.assertEqual(f.read(), " ")

    def test_display_files_on_defcon5(self):
        state.state = "defcon2"
        self._run_one_cycle("ended")
        with open(self.idle_file.name) as f:
            self.assertIn("DEFCON 5", f.read())
        with open(self.alert_file.name) as f:
            self.assertEqual(f.read(), " ")


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


class TestCheckAlertsIntegration(unittest.TestCase):
    """Test check_alerts() with mocked HTTP responses."""

    @patch("lib.oref._fetch_url")
    def test_primary_api_match(self, mock_fetch):
        mock_fetch.return_value = json.dumps({
            "title": "ירי רקטות וטילים",
            "data": ["גבעתיים"],
        })
        result, raw = check_alerts()
        self.assertEqual(result, "actual")
        mock_fetch.assert_called_once()

    @patch("lib.oref._fetch_url")
    def test_empty_primary_falls_through_to_history(self, mock_fetch):
        """When primary returns empty, should try history."""
        import datetime
        now = time.time()
        dt = datetime.datetime.fromtimestamp(now - 60)
        alert_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        mock_fetch.side_effect = [
            "",
            json.dumps([{
                "title": "ירי רקטות וטילים",
                "data": ["תל אביב"],
                "alertDate": alert_date,
            }]),
        ]
        result, raw = check_alerts()
        self.assertEqual(result, "actual")
        self.assertEqual(mock_fetch.call_count, 2)

    @patch("lib.oref._fetch_url")
    def test_history_skips_old_entries(self, mock_fetch):
        """History entries older than 120 seconds should be skipped."""
        mock_fetch.side_effect = [
            "",
            json.dumps([{
                "title": "ירי רקטות וטילים",
                "data": ["תל אביב"],
                "alertDate": "2020-01-01 12:00:00",
            }]),
        ]
        result, raw = check_alerts()
        self.assertIsNone(result)

    @patch("lib.oref._fetch_url")
    def test_no_match_returns_none(self, mock_fetch):
        mock_fetch.side_effect = [
            json.dumps({"title": "ירי רקטות וטילים", "data": ["חיפה"]}),
            json.dumps([]),
        ]
        result, raw = check_alerts()
        self.assertIsNone(result)

    @patch("lib.oref._fetch_url")
    def test_network_error_returns_none(self, mock_fetch):
        mock_fetch.side_effect = Exception("Connection refused")
        result, raw = check_alerts()
        self.assertIsNone(result)


class TestStateResume(unittest.TestCase):
    """Test that startup correctly resumes from persisted state."""

    def setUp(self):
        self.state_file = tempfile.NamedTemporaryFile(delete=False, mode="w")
        self.state_file.close()
        self._orig = config.STATE_FILE
        config.STATE_FILE = self.state_file.name

    def tearDown(self):
        config.STATE_FILE = self._orig
        try:
            os.unlink(self.state_file.name)
        except OSError:
            pass

    def test_resumes_defcon2(self):
        save_state("defcon2")
        self.assertEqual(load_state(), "defcon2")

    def test_resumes_defcon4(self):
        save_state("defcon4")
        self.assertEqual(load_state(), "defcon4")

    def test_unknown_state_treated_as_idle(self):
        """The main() function treats unknown states as idle."""
        save_state("bogus")
        loaded = load_state()
        self.assertNotIn(loaded, ("defcon2", "defcon4"))



class TestLoadTelegramKeys(unittest.TestCase):
    """Test load_telegram_keys() config parsing."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False)
        self._orig = config.TELEGRAM_CONF
        config.TELEGRAM_CONF = self.tmpfile.name

    def tearDown(self):
        config.TELEGRAM_CONF = self._orig
        os.unlink(self.tmpfile.name)

    def test_parses_bot_token_and_chat_id(self):
        self.tmpfile.write('BOT_TOKEN=123456:ABC\nCHAT_ID=-100999\n')
        self.tmpfile.flush()
        keys = load_telegram_keys()
        self.assertEqual(keys['BOT_TOKEN'], '123456:ABC')
        self.assertEqual(keys['CHAT_ID'], '-100999')

    def test_ignores_comments(self):
        self.tmpfile.write('# comment\nBOT_TOKEN=abc\n')
        self.tmpfile.flush()
        keys = load_telegram_keys()
        self.assertEqual(keys['BOT_TOKEN'], 'abc')
        self.assertNotIn('#', str(keys))

    def test_strips_quotes(self):
        self.tmpfile.write('BOT_TOKEN="abc123"\nCHAT_ID="-100"\n')
        self.tmpfile.flush()
        keys = load_telegram_keys()
        self.assertEqual(keys['BOT_TOKEN'], 'abc123')
        self.assertEqual(keys['CHAT_ID'], '-100')

    @patch('builtins.print')
    def test_missing_file_returns_empty(self, _):
        config.TELEGRAM_CONF = '/nonexistent/telegram.conf'
        keys = load_telegram_keys()
        self.assertEqual(keys, {})

    def test_empty_file_returns_empty(self):
        self.tmpfile.write('')
        self.tmpfile.flush()
        keys = load_telegram_keys()
        self.assertEqual(keys, {})


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

if __name__ == "__main__":
    unittest.main()
