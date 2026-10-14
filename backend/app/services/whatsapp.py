"""WhatsApp notifications through CallMeBot (free). Every message is also stored in the outbox."""
from __future__ import annotations

import logging
import time

import httpx

from ..config import get_settings
from ..db import get_setting, session_scope
from ..models import Outbox

log = logging.getLogger(__name__)
CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"
MAX_LEN = 900  # CallMeBot works best with short messages; longer ones are split


def config() -> dict:
    s = get_settings()
    return {"phone": get_setting("whatsapp_phone", s.whatsapp_phone),
            "apikey": get_setting("callmebot_apikey", s.callmebot_apikey)}


def _split(text: str) -> list[str]:
    parts, buf = [], ""
    for para in text.split("\n"):
        if len(buf) + len(para) + 1 > MAX_LEN and buf:
            parts.append(buf)
            buf = ""
        buf += (para + "\n")
    if buf.strip():
        parts.append(buf)
    return parts


def send(text: str, subject: str = "") -> Outbox:
    cfg = config()
    row = Outbox(recipient=cfg["phone"], subject=subject, body=text)
    if not cfg["phone"] or not cfg["apikey"]:
        row.status, row.error = "skipped", "WhatsApp is not configured yet (phone number / CallMeBot API key)"
    else:
        try:
            parts = _split(text)
            for i, part in enumerate(parts):
                r = httpx.get(CALLMEBOT_URL, params={"phone": cfg["phone"], "text": part, "apikey": cfg["apikey"]},
                              timeout=30)
                if r.status_code != 200 or "ERROR" in r.text.upper()[:200]:
                    raise RuntimeError(f"CallMeBot responded {r.status_code}: {r.text[:200]}")
                if i < len(parts) - 1:
                    time.sleep(3)  # CallMeBot rate limits consecutive messages
            row.status = "sent"
        except Exception as e:
            log.warning("WhatsApp send failed: %s", e)
            row.status, row.error = "failed", str(e)[:500]
    with session_scope() as s:
        s.add(row)
        s.commit()
        s.refresh(row)
    return row
