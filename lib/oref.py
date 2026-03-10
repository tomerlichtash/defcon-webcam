"""Pikud HaOref alert API client."""

import json
import sys
import time
import urllib.request

from lib.config import (
    WATCH_TERMS, TITLE_PREEMPTIVE, TITLE_ACTUAL, TITLE_ENDED,
)

URL = "https://www.oref.org.il/warningMessages/alert/Alerts.json"
HISTORY_URL = "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json"

HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.oref.org.il/",
    "User-Agent": "Mozilla/5.0",
}


def _fetch_url(url):
    """Fetch a URL with cache busting and proper encoding handling."""
    cache_bust = url + ("&" if "?" in url else "?") + "t=" + str(int(time.time()))
    req = urllib.request.Request(cache_bust, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=5) as resp:
        raw = resp.read()
        if raw[:2] == b"\xff\xfe":
            return raw.decode("utf-16-le").strip()
        return raw.decode("utf-8-sig").strip()


def _classify_alert(data):
    """Classify alert data. Returns 'preemptive', 'actual', 'ended', or None."""
    cities = data.get("data", [])
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
            print("Unknown alert title: " + title, flush=True)
            return "actual"
    return None


def check_alerts():
    """Check Pikud HaOref API with history fallback."""
    try:
        raw = _fetch_url(URL)
        if raw:
            data = json.loads(raw)
            result = _classify_alert(data)
            if result:
                return result

        raw = _fetch_url(HISTORY_URL)
        if raw:
            history = json.loads(raw)
            if isinstance(history, list):
                now = time.time()
                for entry in history:
                    alert_date = entry.get("alertDate", "")
                    if alert_date:
                        try:
                            import datetime
                            dt = datetime.datetime.strptime(alert_date, "%Y-%m-%d %H:%M:%S")
                            age = now - dt.timestamp()
                            if age > 120:
                                continue
                        except Exception:
                            continue
                    result = _classify_alert(entry)
                    if result:
                        return result
    except Exception as e:
        if "--verbose" in sys.argv:
            print("Error: " + str(e), flush=True)
    return None
