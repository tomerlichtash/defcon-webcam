"""Pikud HaOref alert API client."""

import datetime
import json
import sys
import time
import urllib.request

from lib.alert_log import log_scan
from lib.config import (
    WATCH_TERMS,
    TITLE_PREEMPTIVE,
    TITLE_ACTUAL,
    TITLE_ENDED,
)

URL = "https://www.oref.org.il/warningMessages/alert/Alerts.json"
HISTORY_URL = "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json"

_fail_count = 0
_MAX_BACKOFF = 30  # max extra seconds to wait after repeated failures

HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.oref.org.il/",
    "User-Agent": "Mozilla/5.0",
}


def _fetch_url(url):
    """Fetch a URL with cache busting and proper encoding handling."""
    sep = "&" if "?" in url else "?"
    cache_bust = f"{url}{sep}t={int(time.time())}"
    req = urllib.request.Request(cache_bust, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=5) as resp:
        raw = resp.read()
        if raw[:2] == b"\xff\xfe":
            return raw.decode("utf-16-le").strip()
        return raw.decode("utf-8-sig").strip()


def _classify_alert(data):
    """Classify alert data. Returns 'preemptive', 'actual', 'ended', or None."""
    raw = data.get("data", [])
    # History API returns data as a string (single city), primary API as a list
    cities = raw if isinstance(raw, list) else [raw] if raw else []
    title = data.get("title", "")
    matched = [c for c in cities if any(t in c for t in WATCH_TERMS)]
    if matched:
        if title == TITLE_ENDED:
            return "ended"
        elif title == TITLE_ACTUAL:
            return "actual"
        elif title == TITLE_PREEMPTIVE:
            return "preemptive"
        else:
            print(f"Unknown alert title: {title}", flush=True)
            return "actual"
    return None


def backoff_delay():
    """Return extra delay (seconds) based on consecutive failure count."""
    if _fail_count <= 0:
        return 0
    return min(_fail_count * 2, _MAX_BACKOFF)


def check_alerts():
    """Check Pikud HaOref API with history fallback. Returns (result, raw_data) tuple."""
    global _fail_count
    try:
        raw = _fetch_url(URL)
        if raw:
            data = json.loads(raw)
            result = _classify_alert(data)
            log_scan("primary", raw, result)
            _fail_count = 0
            if result:
                return result, data
        else:
            log_scan("primary", "", None)
            _fail_count = 0

        raw = _fetch_url(HISTORY_URL)
        if raw:
            history = json.loads(raw)
            if isinstance(history, list):
                now = time.time()
                for entry in history:
                    alert_date = entry.get("alertDate", "")
                    if alert_date:
                        try:
                            dt = datetime.datetime.strptime(
                                alert_date, "%Y-%m-%d %H:%M:%S"
                            )
                            age = now - dt.timestamp()
                            if age > 120:
                                continue
                        except Exception:
                            continue
                    result = _classify_alert(entry)
                    if result:
                        log_scan(
                            "history", json.dumps(entry, ensure_ascii=False), result
                        )
                        return result, entry
    except Exception as e:
        _fail_count += 1
        log_scan("error", str(e), None)
        if "--verbose" in sys.argv:
            print(f"Error: {e}", flush=True)
    return None, None
