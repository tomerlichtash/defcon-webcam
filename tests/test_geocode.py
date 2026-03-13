#!/usr/bin/env python3
"""Tests for geocode module — DB operations and lookups."""

import os
import sqlite3
import sys
import tempfile
import unittest

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _root)


class TestGeocodeContextManagers(unittest.TestCase):
    """All geocode DB operations must use context managers (with _conn())."""

    def test_no_manual_conn_close(self):
        """There should be no manual conn.close() calls — use 'with' instead."""
        geo_path = os.path.join(_root, "lib", "geocode.py")
        with open(geo_path) as f:
            source = f.read()
        close_count = source.count("conn.close()")
        self.assertEqual(close_count, 0,
                         f"geocode.py has {close_count} manual conn.close() calls — "
                         "should use 'with _conn() as conn:' context manager instead")

    def test_uses_context_manager(self):
        """DB functions must use 'with _conn()' pattern."""
        geo_path = os.path.join(_root, "lib", "geocode.py")
        with open(geo_path) as f:
            source = f.read()
        context_count = source.count("with _conn()")
        self.assertGreaterEqual(context_count, 6,
                                f"Only {context_count} 'with _conn()' usages — "
                                "expected at least 6 (one per DB function)")


class TestGeocodeFunctions(unittest.TestCase):
    """Test geocode lookup functions with a temporary DB."""

    @classmethod
    def setUpClass(cls):
        cls._orig_path = None
        cls._tmpdb = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmpdb.close()
        import lib.geocode as geo
        cls._orig_path = geo.GEO_DB_PATH
        geo.GEO_DB_PATH = cls._tmpdb.name
        geo.init_geo_db()
        conn = sqlite3.connect(cls._tmpdb.name)
        conn.execute(
            "INSERT INTO cities (name, name_he, lat, lng, source) VALUES (?, ?, ?, ?, ?)",
            ("Tel Aviv", "תל אביב", 32.08, 34.78, "test"),
        )
        conn.execute(
            "INSERT INTO cities (name, name_he, lat, lng, source) VALUES (?, ?, ?, ?, ?)",
            ("Haifa", "חיפה", 32.79, 34.99, "test"),
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        import lib.geocode as geo
        geo.GEO_DB_PATH = cls._orig_path
        os.unlink(cls._tmpdb.name)

    def test_city_count(self):
        from lib.geocode import city_count
        self.assertEqual(city_count(), 2)

    def test_lookup_exact(self):
        from lib.geocode import lookup
        result = lookup("תל אביב")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Tel Aviv")
        self.assertAlmostEqual(result["lat"], 32.08)

    def test_lookup_not_found(self):
        from lib.geocode import lookup
        result = lookup("nonexistent")
        self.assertIsNone(result)

    def test_lookup_fuzzy(self):
        from lib.geocode import lookup_fuzzy
        result = lookup_fuzzy("תל אביב - מרכז")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Tel Aviv")

    def test_lookup_many(self):
        from lib.geocode import lookup_many
        results = lookup_many(["תל אביב", "חיפה", "nonexistent"])
        self.assertEqual(len(results), 2)

    def test_random_cities(self):
        from lib.geocode import random_cities
        results = random_cities(10)
        self.assertEqual(len(results), 2)  # only 2 in DB


if __name__ == "__main__":
    unittest.main()
