"""Telegram group posting logic."""

import json
import urllib.request

from lib import config
from lib.camera import take_alert_snapshot


def send_telegram(text):
    """Send an already-captured snapshot to the Telegram group."""
    keys = config.load_telegram_keys()
    if not keys:
        print("No Telegram keys, skipping message", flush=True)
        return

    bot_token = keys.get("BOT_TOKEN", "")
    chat_id = keys.get("CHAT_ID", "")
    if not bot_token or not chat_id:
        print("Telegram config incomplete, skipping", flush=True)
        return

    url = "https://api.telegram.org/bot" + bot_token + "/sendPhoto"

    boundary = "----DefconCamBoundary"
    body = b""
    body += ("--" + boundary + "\r\n").encode()
    body += b"Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n"
    body += chat_id.encode() + b"\r\n"
    body += ("--" + boundary + "\r\n").encode()
    body += b"Content-Disposition: form-data; name=\"caption\"\r\n\r\n"
    body += text.encode("utf-8") + b"\r\n"
    body += ("--" + boundary + "\r\n").encode()
    body += b"Content-Disposition: form-data; name=\"photo\"; filename=\"snapshot.jpg\"\r\n"
    body += b"Content-Type: image/jpeg\r\n\r\n"
    with open(config.SNAPSHOT_PATH, "rb") as f:
        body += f.read()
    body += b"\r\n"
    body += ("--" + boundary + "--\r\n").encode()

    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
        if result.get("ok"):
            print("Telegram photo sent: " + text, flush=True)
        else:
            print("Telegram API error: " + str(result), flush=True)


def post_telegram(text, mode):
    """Take a snapshot and send it to the Telegram group."""
    try:
        take_alert_snapshot(mode)
        send_telegram(text)
    except Exception as e:
        print("Telegram failed: " + str(e), flush=True)
