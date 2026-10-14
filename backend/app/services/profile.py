"""Owner profile (portfolio data) and work log, rendered as LLM context."""
from __future__ import annotations

import json

from sqlmodel import select

from ..db import session_scope
from ..models import Profile, WorkTask


def get_profile() -> dict:
    with session_scope() as s:
        row = s.get(Profile, 1)
        return json.loads(row.data) if row else {}


def save_profile(data: dict) -> dict:
    with session_scope() as s:
        row = s.get(Profile, 1) or Profile(id=1)
        row.data = json.dumps(data, ensure_ascii=False, indent=1)
        s.add(row)
        s.commit()
    return data


def public_profile() -> dict:
    p = dict(get_profile())
    if not p.get("show_phone_publicly"):
        p.pop("phone", None)
    if not p.get("show_email_publicly", True):
        p.pop("email", None)
    return p


def list_tasks(public_only: bool = False) -> list[WorkTask]:
    with session_scope() as s:
        q = select(WorkTask).order_by(WorkTask.date.desc(), WorkTask.id.desc())
        rows = s.exec(q).all()
        return [t for t in rows if t.public or not public_only]


def _task_line(t: WorkTask) -> str:
    bits = [t.title]
    where = " / ".join(x for x in (t.company, t.project) if x)
    if where:
        bits.append(f"({where})")
    if t.date:
        bits.append(f"[{t.date.isoformat()}]")
    line = " ".join(bits)
    if t.description:
        line += f": {t.description}"
    if t.impact:
        line += f" Impact: {t.impact}"
    if t.tags:
        line += f" Tags: {t.tags}"
    return "- " + line


def profile_context(public: bool) -> str:
    p = public_profile() if public else get_profile()
    tasks = list_tasks(public_only=public)
    parts = ["PROFILE (JSON):", json.dumps(p, ensure_ascii=False, indent=1)]
    if tasks:
        parts += ["", "WORK LOG (tasks and achievements, newest first):"] + [_task_line(t) for t in tasks[:80]]
    return "\n".join(parts)
