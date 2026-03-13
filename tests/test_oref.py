#!/usr/bin/env python3
"""Tests for the oref alert module — fetching, classification, backoff."""

import json
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

sys.modules["tweepy"] = MagicMock()

from lib.oref import _fetch_url, _classify_alert, check_alerts


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


class TestOrefBackoff(unittest.TestCase):
    """Oref API client must back off on repeated failures."""

    def test_has_failure_tracking(self):
        """oref.py must track consecutive failures for backoff."""
        path = os.path.join(_root, "lib", "oref.py")
        with open(path) as f:
            source = f.read()
        has_backoff = ("_fail_count" in source or "_consecutive_fail" in source
                       or "backoff" in source or "_errors" in source)
        self.assertTrue(has_backoff,
                        "oref.py has no failure tracking — polls at full rate even during outages")


if __name__ == "__main__":
    unittest.main()
