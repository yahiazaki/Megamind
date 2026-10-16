"""Admin study sessions: chat stream, quizzes and grading."""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import delete, select

from ..db import session_scope
from ..models import ChatSession, Message, QuizItem
from ..security import require_admin
from ..services import study

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_admin)])


class MessageIn(BaseModel):
    text: str
    mentions: list[int] = []  # @mentioned notes from the workspace


class GradeIn(BaseModel):
    answers: dict[int, str]


def _session_dict(sess: ChatSession) -> dict:
    return {"id": sess.id, "title": sess.title, "created_at": sess.created_at, "ended_at": sess.ended_at,
            "summary": json.loads(sess.summary) if sess.summary else None}


@router.get("")
def list_sessions():
    with session_scope() as s:
        return [_session_dict(x) for x in s.exec(select(ChatSession).where(ChatSession.mode == "study")
                                                  .order_by(ChatSession.id.desc())).all()]


@router.post("")
def create_session():
    with session_scope() as s:
        sess = ChatSession()
        s.add(sess)
        s.commit()
        s.refresh(sess)
        return _session_dict(sess)


@router.get("/{session_id}")
def get_session(session_id: int):
    with session_scope() as s:
        sess = s.get(ChatSession, session_id)
        if not sess:
            raise HTTPException(404)
        msgs = s.exec(select(Message).where(Message.session_id == session_id).order_by(Message.id)).all()
        quiz = {q.id: q for q in s.exec(select(QuizItem).where(QuizItem.session_id == session_id)).all()}
        out = []
        for m in msgs:
            payload = json.loads(m.payload) if m.payload else {}
            item = {"id": m.id, "role": m.role, "content": m.content, "kind": m.kind, "created_at": m.created_at}
            if m.kind in ("quiz", "quiz_result"):
                item["items"] = [study.quiz_public(quiz[i]) for i in payload.get("ids", []) if i in quiz]
            elif m.kind == "summary":
                item["data"] = payload
            elif m.kind == "reminder":
                item["data"] = payload
            else:
                item["sources"] = payload.get("sources", [])
            out.append(item)
        return {"session": _session_dict(sess), "messages": out}


@router.delete("/{session_id}")
def delete_session(session_id: int):
    with session_scope() as s:
        s.exec(delete(QuizItem).where(QuizItem.session_id == session_id))
        s.exec(delete(Message).where(Message.session_id == session_id))
        sess = s.get(ChatSession, session_id)
        if sess:
            s.delete(sess)
        s.commit()
    return {"ok": True}


@router.post("/{session_id}/messages")
def post_message(session_id: int, body: MessageIn):
    with session_scope() as s:
        if not s.get(ChatSession, session_id):
            raise HTTPException(404)
    return StreamingResponse(study.handle_message(session_id, body.text, body.mentions), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{session_id}/grade")
def grade(session_id: int, body: GradeIn):
    return {"results": study.grade(session_id, body.answers)}
