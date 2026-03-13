"""Geocoding cache — maps city names to coordinates using a dedicated SQLite DB."""

import os
import json
import sqlite3
import tempfile
import time
import urllib.request

GEO_DB_PATH = os.path.join(tempfile.gettempdir(), "defcon-geocode.db")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:60];
area["ISO3166-1"="IL"]->.a;
(
  node["place"~"city|town|village"](area.a);
);
out body;
"""

OREF_CITIES_URL = "https://www.oref.org.il/Shared/Ajax/GetCitiesMix.aspx?lang=he"


def _conn():
    conn = sqlite3.connect(GEO_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row):
    """Convert a sqlite3.Row to a city dict."""
    return {
        "name": row["name"],
        "name_he": row["name_he"],
        "lat": row["lat"],
        "lng": row["lng"],
    }


def init_geo_db():
    """Create the geocode table if it doesn't exist."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                name TEXT PRIMARY KEY,
                name_he TEXT,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                source TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_name_he ON cities(name_he)")


def city_count():
    """Return number of cities in the geocode DB."""
    try:
        with _conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM cities").fetchone()
            return row[0]
    except Exception:
        return 0


def lookup(name):
    """Look up a city by Hebrew name. Returns {name, name_he, lat, lng} or None."""
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT name, name_he, lat, lng FROM cities WHERE name_he = ? OR name = ?",
                (name, name),
            ).fetchone()
            if row:
                return _row_to_dict(row)
    except Exception:
        pass
    return None


def lookup_fuzzy(name):
    """Fuzzy lookup — matches if the query is a substring of the city name or vice versa."""
    result = lookup(name)
    if result:
        return result
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT name, name_he, lat, lng FROM cities "
                "WHERE name_he LIKE ? OR name LIKE ? "
                "OR ? LIKE '%' || name_he || '%' OR ? LIKE '%' || name || '%' "
                "LIMIT 1",
                (f"%{name}%", f"%{name}%", name, name),
            ).fetchone()
            if row:
                return _row_to_dict(row)
    except Exception:
        pass
    return None


def lookup_many(names):
    """Look up multiple city names. Returns list of {name, name_he, lat, lng} for found cities."""
    results = []
    for name in names:
        r = lookup_fuzzy(name)
        if r:
            results.append(r)
    return results


def random_cities(count=100):
    """Return a random sample of cities from the DB."""
    try:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT name, name_he, lat, lng FROM cities ORDER BY RANDOM() LIMIT ?",
                (count,),
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
    except Exception:
        return []


def populate_from_overpass():
    """Fetch all Israeli cities/towns/villages from Overpass API and store in DB."""
    print("Fetching cities from Overpass API...", flush=True)
    req = urllib.request.Request(
        OVERPASS_URL, data=b"data=" + urllib.request.quote(OVERPASS_QUERY).encode()
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    elements = result.get("elements", [])
    print(f"Got {len(elements)} places from Overpass", flush=True)

    with _conn() as conn:
        count = 0
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name", "")
            name_he = tags.get("name:he", name)
            lat = el.get("lat")
            lon = el.get("lon")
            if not name or not lat or not lon:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO cities (name, name_he, lat, lng, source) VALUES (?, ?, ?, ?, ?)",
                (name, name_he, lat, lon, "overpass"),
            )
            count += 1
    print(f"Stored {count} cities in {GEO_DB_PATH}", flush=True)
    return count
