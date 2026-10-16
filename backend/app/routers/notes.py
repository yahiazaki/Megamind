"""Notes workspace API (owner only)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..security import require_admin
from ..services import notes

router = APIRouter(prefix="/api/notes", dependencies=[Depends(require_admin)])


class NoteIn(BaseModel):
    title: Optional[str] = None
    html: Optional[str] = None
    markdown: Optional[str] = None


class AssistIn(BaseModel):
    instruction: str
    selection: str = ""
    mentions: list[int] = []
    use_book: bool = True
    markdown: Optional[str] = None  # unsaved editor content


class PublishIn(BaseModel):
    part: str
    polish: bool = False


def _note_or_404(note_id: int):
    n = notes.get(note_id)
    if not n:
        raise HTTPException(404, "Note not found")
    return n


@router.get("")
def list_notes():
    return notes.list_notes()


@router.get("/parts")
def parts():
    return notes.book_parts()


@router.post("")
def create(body: NoteIn):
    return notes.full(notes.create(body.title or "Untitled", body.html or "", body.markdown or ""))


@router.get("/{note_id}")
def get(note_id: int):
    return notes.full(_note_or_404(note_id))


@router.put("/{note_id}")
def update(note_id: int, body: NoteIn):
    _note_or_404(note_id)
    return notes.summary(notes.update(note_id, body.title, body.html, body.markdown))


@router.delete("/{note_id}")
def delete(note_id: int, remove_from_book: bool = False):
    _note_or_404(note_id)
    notes.delete(note_id, remove_from_book)
    return {"ok": True}


@router.get("/{note_id}/export")
async def export(note_id: int, format: str = "docx"):
    _note_or_404(note_id)
    try:
        path, name = await run_in_threadpool(notes.export, note_id, format)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Export failed: {e}")
    return FileResponse(path, filename=name)


@router.post("/{note_id}/assist")
async def assist(note_id: int, body: AssistIn):
    _note_or_404(note_id)
    if not body.instruction.strip():
        raise HTTPException(400, "Write what you want the assistant to do")
    try:
        return await run_in_threadpool(notes.assist, note_id, body.instruction, body.selection, body.mentions,
                                       body.use_book, body.markdown)
    except Exception as e:
        raise HTTPException(500, f"The assistant failed: {e}")


@router.post("/{note_id}/publish")
def publish(note_id: int, body: PublishIn):
    _note_or_404(note_id)
    try:
        return notes.publish(note_id, body.part, body.polish)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{note_id}/unpublish")
def unpublish(note_id: int):
    _note_or_404(note_id)
    notes.unpublish(note_id)
    return {"ok": True}
