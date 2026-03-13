#!/usr/bin/env python3
"""Tests for configuration parsing — modes, keys, error handling."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

sys.modules["tweepy"] = MagicMock()

from lib import config
from lib.config import get_current_mode, load_twitter_keys, load_telegram_keys


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


class TestConfigLogging(unittest.TestCase):
    """_parse_conf must log errors, not silently return empty dict."""

    def test_parse_conf_logs_errors(self):
        """_parse_conf should log when config file is malformed."""
        import re
        path = os.path.join(_root, "lib", "config.py")
        with open(path) as f:
            source = f.read()
        fn_start = source.find("def _parse_conf(")
        fn_end = source.find("\ndef ", fn_start + 1)
        fn_body = source[fn_start:fn_end]
        has_silent = re.search(r"except\s+Exception\s*:\s*\n\s*pass", fn_body)
        self.assertIsNone(has_silent,
                          "_parse_conf silently swallows all errors — "
                          "should at least log FileNotFoundError vs parse errors")


if __name__ == "__main__":
    unittest.main()
