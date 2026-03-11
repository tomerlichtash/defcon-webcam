"""Alert event log."""

import json
import os
import time

LOG_FILE = "/tmp/mjpg-alert-log.json"
MAX_ENTRIES = 100


def log_event(defcon, raw_data=None):
    """Append a DEFCON state change to the log file."""
    entry = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "defcon": defcon,
    }
    if raw_data:
        entry["raw"] = raw_data

    entries = load_log()
    entries.insert(0, entry)
    entries = entries[:MAX_ENTRIES]

    try:
        with open(LOG_FILE, "w") as f:
            json.dump(entries, f, ensure_ascii=False)
    except Exception:
        pass


def load_log():
    """Load the event log from disk."""
    try:
        with open(LOG_FILE) as f:
            return json.load(f)
    except Exception:
        return []


SCAN_LOG_FILE = "/tmp/mjpg-scan-log.json"
MAX_SCAN_ENTRIES = 50


def log_scan(source, raw_text, result):
    """Log every API poll result for debugging."""
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "source": source,
        "result": result,
        "data": raw_text[:500] if raw_text else "",
    }

    entries = load_scan_log()
    entries.insert(0, entry)
    entries = entries[:MAX_SCAN_ENTRIES]

    try:
        with open(SCAN_LOG_FILE, "w") as f:
            json.dump(entries, f, ensure_ascii=False)
    except Exception:
        pass


def load_scan_log():
    """Load the scan log from disk."""
    try:
        with open(SCAN_LOG_FILE) as f:
            return json.load(f)
    except Exception:
        return []
