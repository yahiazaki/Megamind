"""Background schedule: the daily WhatsApp briefing of today's reminders and calendar events."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import get_settings
from ..db import get_setting
from . import reminders, whatsapp

log = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=get_settings().timezone)
JOB_ID = "daily-briefing"


def briefing_time() -> str:
    return get_setting("daily_briefing_time", get_settings().daily_briefing_time)


def send_daily_briefing() -> dict:
    text = reminders.daily_briefing()
    row = whatsapp.send(text, subject="Daily briefing")
    log.info("daily briefing: %s", row.status)
    return {"status": row.status, "error": row.error, "text": text}


def schedule() -> None:
    hh, mm = (int(x) for x in briefing_time().split(":"))
    scheduler.add_job(send_daily_briefing, CronTrigger(hour=hh, minute=mm), id=JOB_ID, replace_existing=True,
                      misfire_grace_time=3600, coalesce=True)


def start() -> None:
    schedule()
    if not scheduler.running:
        scheduler.start()


def next_run() -> str | None:
    job = scheduler.get_job(JOB_ID)
    return job.next_run_time.isoformat() if job and job.next_run_time else None
