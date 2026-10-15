"""Reminders live in the local DB and are mirrored to Google Calendar when it is connected."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import select

from .. import llm
from ..config import get_settings
from ..db import session_scope
from ..models import Reminder
from . import gcal

log = logging.getLogger(__name__)

PARSE_SYSTEM = """You extract a reminder from a message (English, Egyptian Arabic or Franco-Arabic).
Today is {today} ({weekday}); current time {now}; timezone {tz}.
Return JSON: {{"title": "<short English title>", "notes": "<details or empty>",
"start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM or empty", "all_day": true|false}}
Rules: resolve relative dates ("tomorrow", "bokra", "next Monday", "el sabt"). If no time is given use all_day=true
and 09:00 as the start time. Keep the title short and actionable."""


def create(title: str, start: datetime, end: datetime | None = None, notes: str = "",
           all_day: bool = False) -> Reminder:
    event_id = ""
    try:
        event_id = gcal.create_event(title, start, end, notes, all_day)
    except Exception as e:
        log.warning("Google Calendar sync failed: %s", e)
    with session_scope() as s:
        r = Reminder(title=title, notes=notes, start=start, end=end, all_day=all_day, google_event_id=event_id)
        s.add(r)
        s.commit()
        s.refresh(r)
        return r


def sync_pending() -> int:
    """Copy upcoming reminders that were saved while Google was not connected. Returns how many were synced."""
    now = datetime.now()
    synced = 0
    with session_scope() as s:
        rows = s.exec(select(Reminder).where(Reminder.google_event_id == "", Reminder.start >= now - timedelta(hours=1))).all()
        for r in rows:
            try:
                r.google_event_id = gcal.create_event(r.title, r.start, r.end, r.notes, r.all_day)
            except Exception as e:
                log.warning("Google Calendar sync failed for reminder %s: %s", r.id, e)
                continue
            if r.google_event_id:
                s.add(r)
                synced += 1
        s.commit()
    return synced


def parse_and_create(message: str) -> Reminder:
    tz = get_settings().timezone
    now = datetime.now(ZoneInfo(tz))
    system = PARSE_SYSTEM.format(today=now.date().isoformat(), weekday=now.strftime("%A"),
                                 now=now.strftime("%H:%M"), tz=tz)
    data = llm.chat_json(system, message)
    start = datetime.fromisoformat(data["start"])
    end = datetime.fromisoformat(data["end"]) if data.get("end") else None
    return create(data.get("title") or message[:60], start, end, data.get("notes", ""), bool(data.get("all_day")))


def delete(reminder_id: int) -> None:
    with session_scope() as s:
        r = s.get(Reminder, reminder_id)
        if r:
            gcal.delete_event(r.google_event_id)
            s.delete(r)
            s.commit()


def for_day(day: date) -> list[Reminder]:
    with session_scope() as s:
        start = datetime.combine(day, datetime.min.time())
        rows = s.exec(select(Reminder).where(Reminder.start >= start, Reminder.start < start + timedelta(days=1))
                      .order_by(Reminder.start)).all()
        return list(rows)


def daily_briefing(day: date | None = None) -> str:
    day = day or datetime.now(ZoneInfo(get_settings().timezone)).date()
    local = for_day(day)
    try:
        google = gcal.events_for(day)
    except Exception as e:
        log.warning("Google Calendar read failed: %s", e)
        google = []
    synced_ids = {r.google_event_id for r in local if r.google_event_id}
    lines = [f"🧠 *Megamind — your plan for {day.strftime('%A %d %B')}*", ""]
    items = []
    for r in local:
        when = "All day" if r.all_day else r.start.strftime("%H:%M")
        items.append((r.start.strftime("%H:%M") if not r.all_day else "00:00",
                      f"• {when} — {r.title}" + (f"\n   {r.notes}" if r.notes else "")))
    for ev in google:
        if ev["id"] in synced_ids:
            continue
        when = "All day" if ev["all_day"] else ev["start"][11:16]
        items.append((when if not ev["all_day"] else "00:00", f"• {when} — {ev['title']}"))
    if not items:
        lines.append("Nothing scheduled today. A good day for a study session! 📚")
    else:
        lines += [text for _, text in sorted(items)]
    return "\n".join(lines)
