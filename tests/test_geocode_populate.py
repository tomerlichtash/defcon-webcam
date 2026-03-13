#!/usr/bin/env python3
"""Tests for geocode populate_from_overpass with mocked HTTP."""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)

import lib.geocode as geocode


class TestPopulateFromOverpass(unittest.TestCase):
    """Test populate_from_overpass with mocked HTTP responses."""

    def setUp(self):
        self._orig_path = geocode.GEO_DB_PATH
        fd, self._tmpdb = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        geocode.GEO_DB_PATH = self._tmpdb
        geocode.init_geo_db()

    def tearDown(self):
        geocode.GEO_DB_PATH = self._orig_path
        try:
            os.unlink(self._tmpdb)
        except OSError:
            pass

    def _mock_overpass_response(self, elements):
        """Create a mock urlopen response with Overpass-format data."""
        data = json.dumps({"elements": elements}).encode("utf-8")
        resp = MagicMock()
        resp.read.return_value = data
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    @patch("builtins.print")
    @patch("urllib.request.urlopen")
    def test_imports_cities(self, mock_urlopen, _):
        elements = [
            {"tags": {"name": "Tel Aviv", "name:he": "תל אביב"}, "lat": 32.08, "lon": 34.78},
            {"tags": {"name": "Haifa", "name:he": "חיפה"}, "lat": 32.79, "lon": 34.99},
        ]
        mock_urlopen.return_value = self._mock_overpass_response(elements)

        count = geocode.populate_from_overpass()
        self.assertEqual(count, 2)
        self.assertEqual(geocode.city_count(), 2)

    @patch("builtins.print")
    @patch("urllib.request.urlopen")
    def test_skips_elements_without_coords(self, mock_urlopen, _):
        elements = [
            {"tags": {"name": "Good City", "name:he": "עיר טובה"}, "lat": 31.0, "lon": 34.0},
            {"tags": {"name": "No Coords"}, "lat": None, "lon": None},
            {"tags": {"name": ""}, "lat": 32.0, "lon": 35.0},  # empty name
        ]
        mock_urlopen.return_value = self._mock_overpass_response(elements)

        count = geocode.populate_from_overpass()
        self.assertEqual(count, 1)

    @patch("builtins.print")
    @patch("urllib.request.urlopen")
    def test_upserts_on_duplicate(self, mock_urlopen, _):
        """Running populate twice should update, not duplicate."""
        elements = [
            {"tags": {"name": "Tel Aviv", "name:he": "תל אביב"}, "lat": 32.08, "lon": 34.78},
        ]
        mock_urlopen.return_value = self._mock_overpass_response(elements)
        geocode.populate_from_overpass()

        # Update coordinates
        elements[0]["lat"] = 32.09
        mock_urlopen.return_value = self._mock_overpass_response(elements)
        geocode.populate_from_overpass()

        self.assertEqual(geocode.city_count(), 1)
        result = geocode.lookup("תל אביב")
        self.assertAlmostEqual(result["lat"], 32.09)

    @patch("builtins.print")
    @patch("urllib.request.urlopen")
    def test_uses_name_as_name_he_fallback(self, mock_urlopen, _):
        """If name:he is missing, name should be used as name_he."""
        elements = [
            {"tags": {"name": "Jaffa"}, "lat": 32.05, "lon": 34.75},
        ]
        mock_urlopen.return_value = self._mock_overpass_response(elements)
        geocode.populate_from_overpass()

        result = geocode.lookup("Jaffa")
        self.assertIsNotNone(result)
        self.assertEqual(result["name_he"], "Jaffa")


if __name__ == "__main__":
    unittest.main()
