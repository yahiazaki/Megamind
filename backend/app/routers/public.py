"""Public endpoints: portfolio profile, recruiter chat, and admin login."""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import security
from ..services import portfolio, profile

router = APIRouter(prefix="/api")
_hits: dict[str, deque] = defaultdict(deque)
PUBLIC_LIMIT = 30  # questions per IP per hour (protects the local GPU)


class LoginIn(BaseModel):
    password: str


class PublicChatIn(BaseModel):
    question: str
    history: list[dict] = []


@router.post("/auth/login")
def login(body: LoginIn, response: Response):
    if not security.check_password(body.password):
        time.sleep(1)
        raise HTTPException(401, "Wrong password")
    security.login(response)
    return {"admin": True}


@router.post("/auth/logout")
def logout(response: Response):
    security.logout(response)
    return {"admin": False}


@router.get("/auth/me")
def me(mm_admin: str | None = Cookie(default=None)):
    return {"admin": security.is_admin(mm_admin)}


@router.get("/public/profile")
def public_profile():
    tasks = [{"title": t.title, "company": t.company, "project": t.project, "date": t.date, "impact": t.impact,
              "tags": t.tags} for t in profile.list_tasks(public_only=True)[:20]]
    return {"profile": profile.public_profile(), "recent_work": tasks}


@router.post("/public/chat")
def public_chat(body: PublicChatIn, request: Request, mm_admin: str | None = Cookie(default=None)):
    if not security.is_admin(mm_admin):
        ip = request.client.host if request.client else "?"
        q = _hits[ip]
        now = time.time()
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= PUBLIC_LIMIT:
            raise HTTPException(429, "Too many questions — please try again later")
        q.append(now)
    return StreamingResponse(portfolio.stream_public_answer(body.question, body.history),
                             media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
