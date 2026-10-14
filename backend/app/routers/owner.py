"""Admin: profile, work log, CV generator, reminders, settings, integrations and outbox."""
import datetime as dt
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlmodel import select

from .. import llm
from ..config import get_settings
from ..db import all_settings, session_scope, set_setting
from ..models import Outbox, Reminder, WorkTask
from ..security import require_admin
from ..services import cv, gcal, profile, reminders, scheduler, whatsapp

router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])

# ---------------------------------------------------------------- profile + work log


@router.get("/profile")
def get_profile():
    return profile.get_profile()


@router.put("/profile")
def put_profile(data: dict):
    return profile.save_profile(data)


class TaskIn(BaseModel):
    title: str
    description: str = ""
    company: str = ""
    project: str = ""
    tags: str = ""
    impact: str = ""
    date: dt.date | None = None
    public: bool = True


@router.get("/tasks")
def tasks():
    return [t.model_dump() for t in profile.list_tasks()]


@router.post("/tasks")
def add_task(body: TaskIn):
    with session_scope() as s:
        t = WorkTask(**body.model_dump())
        s.add(t)
        s.commit()
        s.refresh(t)
        return t.model_dump()


@router.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskIn):
    with session_scope() as s:
        t = s.get(WorkTask, task_id)
        if not t:
            raise HTTPException(404)
        for k, v in body.model_dump().items():
            setattr(t, k, v)
        s.add(t)
        s.commit()
        s.refresh(t)
        return t.model_dump()


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    with session_scope() as s:
        t = s.get(WorkTask, task_id)
        if t:
            s.delete(t)
            s.commit()
    return {"ok": True}

# ---------------------------------------------------------------- CV generator


class CvIn(BaseModel):
    job_description: str
    target_title: str = ""
    extra: str = ""


@router.post("/cv")
def generate_cv(body: CvIn):
    if len(body.job_description.strip()) < 30:
        raise HTTPException(400, "Paste the job description (at least a few lines)")
    return cv.generate(body.job_description, body.extra, body.target_title)


@router.get("/cv")
def list_cvs():
    return cv.list_generated()


@router.get("/cv/{cv_id}/{ext}")
def cv_file(cv_id: str, ext: str):
    p = cv.file_for(cv_id, ext)
    if not p:
        raise HTTPException(404)
    media = "application/pdf" if ext == "pdf" else \
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(p, media_type=media, filename=f"Yahia_Zaki_CV_{cv_id[:15]}.{ext}",
                        content_disposition_type="inline" if ext == "pdf" else "attachment")

# ---------------------------------------------------------------- reminders


class ReminderIn(BaseModel):
    title: str
    start: datetime
    end: datetime | None = None
    notes: str = ""
    all_day: bool = False


class ReminderText(BaseModel):
    text: str


def _rem(r: Reminder) -> dict:
    return r.model_dump() | {"google": bool(r.google_event_id)}


@router.get("/reminders")
def list_reminders(upcoming: bool = True):
    with session_scope() as s:
        q = select(Reminder).order_by(Reminder.start)
        if upcoming:
            q = q.where(Reminder.start >= datetime.combine(date.today(), datetime.min.time()))
        return [_rem(r) for r in s.exec(q).all()]


@router.post("/reminders")
def add_reminder(body: ReminderIn):
    return _rem(reminders.create(body.title, body.start, body.end, body.notes, body.all_day))


@router.post("/reminders/parse")
def add_reminder_text(body: ReminderText):
    return _rem(reminders.parse_and_create(body.text))


@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int):
    reminders.delete(reminder_id)
    return {"ok": True}


@router.get("/briefing/preview")
def briefing_preview():
    return {"text": reminders.daily_briefing(), "next_run": scheduler.next_run()}


@router.post("/briefing/send")
def briefing_send():
    return scheduler.send_daily_briefing()

# ---------------------------------------------------------------- settings + integrations

EDITABLE = {"whatsapp_phone", "callmebot_apikey", "daily_briefing_time", "chat_model", "llm_provider",
            "anthropic_base_url", "anthropic_api_key", "anthropic_model"}
SECRET = {"callmebot_apikey", "anthropic_api_key"}


@router.get("/settings")
def get_settings_view():
    s = get_settings()
    stored = all_settings()
    out = {}
    for key in sorted(EDITABLE):
        val = stored.get(key) or str(getattr(s, key, "") or "")
        out[key] = ("•" * 8 + val[-4:]) if key in SECRET and val else val
    return {"values": out, "llm": llm.status(), "google": gcal.status(), "briefing_next_run": scheduler.next_run(),
            "timezone": s.timezone}


@router.put("/settings")
def put_settings(values: dict):
    for k, v in values.items():
        if k in EDITABLE and isinstance(v, str) and not v.startswith("••••"):
            if k == "daily_briefing_time":
                try:
                    datetime.strptime(v, "%H:%M")
                except ValueError:
                    raise HTTPException(400, "Briefing time must be HH:MM")
            set_setting(k, v.strip())
    scheduler.schedule()
    return get_settings_view()


@router.post("/whatsapp/test")
def whatsapp_test():
    row = whatsapp.send("✅ Megamind is connected to your WhatsApp. Study summaries and daily plans will arrive here.",
                        subject="Test")
    return {"status": row.status, "error": row.error}


@router.get("/outbox")
def outbox(limit: int = 30):
    with session_scope() as s:
        return [o.model_dump() for o in s.exec(select(Outbox).order_by(Outbox.id.desc()).limit(limit)).all()]


@router.get("/google/auth")
def google_auth():
    try:
        return {"url": gcal.auth_url()}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/google/callback")
def google_callback(state: str, code: str):
    try:
        gcal.finish_auth(state, code)
        return RedirectResponse("/admin/settings?google=connected")
    except Exception as e:
        return RedirectResponse(f"/admin/settings?google=error&message={str(e)[:120]}")


@router.post("/google/disconnect")
def google_disconnect():
    gcal.disconnect()
    return gcal.status()
