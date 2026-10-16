"""Notes workspace: pages written in the editor, an AI writing assistant, export, and publishing into the book."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from sqlmodel import func, select

from .. import llm
from ..config import get_settings
from ..db import session_scope
from ..ingest import convert
from ..models import Document, Note
from ..rag.index import build_queries, citations_json, format_context, index

log = logging.getLogger(__name__)

NOTE_LIMIT = 8000       # characters of the open note sent to the model
MENTION_LIMIT = 3000    # characters per @mentioned note
WHOLE_NOTE_LIMIT = 6000  # longer notes are never rewritten in one go (the model would drop content)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def summary(n: Note) -> dict:
    return {"id": n.id, "title": n.title, "updated_at": n.updated_at.isoformat(), "in_book": bool(n.document_id),
            "book_part": n.book_part, "published_at": n.published_at.isoformat() if n.published_at else None,
            "stale": bool(n.published_at and n.updated_at > n.published_at)}


def full(n: Note) -> dict:
    d = summary(n) | {"html": n.html, "markdown": n.markdown}
    if n.document_id:
        with session_scope() as s:
            doc = s.get(Document, n.document_id)
            if doc:
                d |= {"document_status": doc.status, "book_page": doc.book_start_page, "document_error": doc.error}
    return d


def list_notes() -> list[dict]:
    with session_scope() as s:
        return [summary(n) for n in s.exec(select(Note).order_by(Note.updated_at.desc())).all()]


def get(note_id: int) -> Note | None:
    with session_scope() as s:
        return s.get(Note, note_id)


def create(title: str = "Untitled", html: str = "", markdown: str = "") -> Note:
    with session_scope() as s:
        n = Note(title=title.strip() or "Untitled", html=html, markdown=markdown)
        s.add(n)
        s.commit()
        s.refresh(n)
        return n


def update(note_id: int, title: str | None = None, html: str | None = None, markdown: str | None = None) -> Note:
    with session_scope() as s:
        n = s.get(Note, note_id)
        if not n:
            raise KeyError(note_id)
        if title is not None:
            n.title = title.strip() or "Untitled"
        if html is not None:
            n.html = html
        if markdown is not None:
            n.markdown = markdown
        n.updated_at = datetime.now()
        s.add(n)
        s.commit()
        s.refresh(n)
        return n


def delete(note_id: int, remove_from_book: bool = False) -> None:
    doc_id = None
    with session_scope() as s:
        n = s.get(Note, note_id)
        if n:
            doc_id = n.document_id
            s.delete(n)
            s.commit()
    if doc_id and remove_from_book:
        from ..ingest.pipeline import delete_document
        delete_document(doc_id)


def find_by_titles(titles: list[str]) -> list[Note]:
    wanted = {t.strip().lower() for t in titles if t.strip()}
    with session_scope() as s:
        return [n for n in s.exec(select(Note)).all() if n.title.strip().lower() in wanted]


def mention_context(note_ids: list[int], exclude: int | None = None) -> str:
    """Text block with the contents of @mentioned notes, for the assistant or the study chat."""
    parts = []
    with session_scope() as s:
        for nid in dict.fromkeys(note_ids):
            n = s.get(Note, nid)
            if n and n.id != exclude:
                body = n.markdown.strip() or convert.html_to_text(n.html)
                parts.append(f'--- NOTE "@{n.title}" ---\n{body[:MENTION_LIMIT]}')
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _safe_name(title: str) -> str:
    return re.sub(r"[^\w\- ]+", "", title).strip()[:60] or "note"


def export(note_id: int, fmt: str) -> tuple[Path, str]:
    """Returns (file path, download name)."""
    n = get(note_id)
    if not n:
        raise KeyError(note_id)
    out_dir = get_settings().data_dir / "tmp" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = _safe_name(n.title)
    out = out_dir / f"note-{n.id}.{fmt}"
    if fmt == "md":
        out.write_text(f"# {n.title}\n\n{n.markdown}", encoding="utf-8")
    elif fmt == "txt":
        out.write_text(f"{n.title}\n\n{convert.html_to_text(n.html)}", encoding="utf-8")
    elif fmt in ("docx", "pdf"):
        convert.html_export(n.html, n.title, out, fmt)
    else:
        raise ValueError("format must be docx, pdf, txt or md")
    return out, f"{name}.{fmt}"


# ---------------------------------------------------------------------------
# Publish into the book + RAG
# ---------------------------------------------------------------------------

def book_parts() -> list[str]:
    """Parts of the book (document subjects) in book order."""
    with session_scope() as s:
        rows = s.exec(select(Document.subject, func.min(Document.sort_order)).group_by(Document.subject)).all()
    return [r[0] for r in sorted(rows, key=lambda r: r[1]) if r[0]]


def _sort_order_for(part: str, doc_id: int | None) -> float:
    with session_scope() as s:
        if doc_id:
            d = s.get(Document, doc_id)
            if d and d.subject == part:
                return d.sort_order
        in_part = s.exec(select(func.max(Document.sort_order)).where(Document.subject == part)).one()
        if in_part is not None:
            # just after the part's last chapter, before the next part
            nxt = s.exec(select(func.min(Document.sort_order)).where(Document.sort_order > in_part)).one()
            return (in_part + nxt) / 2 if nxt is not None else in_part + 1
        top = s.exec(select(func.max(Document.sort_order))).one()
        return (top or 0) + 10


def publish(note_id: int, part: str, polish: bool = False) -> dict:
    """Write the note as a markdown source and (re)ingest it as a chapter of the given part of the book."""
    from ..ingest.pipeline import queue_ingest

    n = get(note_id)
    if not n:
        raise KeyError(note_id)
    if not (n.markdown.strip() or n.html.strip()):
        raise ValueError("The note is empty")
    part = part.strip() or "Notes"
    src = get_settings().data_dir / "notes" / f"note-{n.id}.md"
    src.write_text(f"# {n.title}\n\n{n.markdown.strip()}\n", encoding="utf-8")
    with session_scope() as s:
        doc = s.get(Document, n.document_id) if n.document_id else None
        order = _sort_order_for(part, doc.id if doc else None)
        if doc is None:
            doc = Document(title=n.title, subject=part, kind="workspace", source_path=str(src), translate=False)
        doc.title, doc.subject, doc.sort_order, doc.source_path = n.title, part, order, str(src)
        doc.status, doc.error, doc.polish = "pending", "", polish
        s.add(doc)
        s.commit()
        s.refresh(doc)
        note = s.get(Note, n.id)
        note.document_id, note.book_part, note.published_at = doc.id, part, datetime.now()
        s.add(note)
        s.commit()
        doc_id = doc.id
    job_id = queue_ingest(doc_id)
    return {"document_id": doc_id, "job_id": job_id}


def unpublish(note_id: int) -> None:
    from ..ingest.pipeline import delete_document

    with session_scope() as s:
        n = s.get(Note, note_id)
        if not n or not n.document_id:
            return
        doc_id = n.document_id
        n.document_id, n.book_part, n.published_at = None, "", None
        s.add(n)
        s.commit()
    delete_document(doc_id)


# ---------------------------------------------------------------------------
# AI writing assistant
# ---------------------------------------------------------------------------

ASSIST_SYSTEM = """You are Megamind's writing assistant inside Yahia's notes editor. You help him write and edit
study notes. Decide the right action and return JSON:
{"action": "insert" | "replace_selection" | "replace_note" | "reply",
 "content": "markdown",
 "used_book": true | false,
 "message": "one short sentence saying what you did and whether it came from his book or your own knowledge"}

Actions:
- "insert": he asks to add, write, explain or expand something. content = only the NEW text to add; do not repeat
  headings or sentences that are already in the note.
- "replace_selection": he selected text (SELECTED TEXT is given) and asks to rewrite, fix, shorten, translate or
  reformat it. content = the replacement for exactly that selection.
- "replace_note": only when he explicitly asks to rewrite, restructure or clean up the WHOLE note. content = the full
  new note; keep every piece of information.
- "reply": he asks a question and does not want the note changed. content = the answer.

Knowledge: use BOOK EXCERPTS and MENTIONED NOTES when they actually cover the request. If they do not, write from your
own knowledge — that is fine and expected. Set used_book to true only if you actually used the book excerpts or
mentioned notes. Never invent citations, and do not put excerpt numbers in the note text.
Style: English, clean markdown (## headings, - bullets, **bold**, `code`, tables when useful), concise and accurate,
matching the tone of the existing note. Do not repeat the note's title as a heading."""


def assist(note_id: int, instruction: str, selection: str = "", mentions: list[int] | None = None,
           use_book: bool = True, note_markdown: str | None = None) -> dict:
    n = get(note_id)
    if not n:
        raise KeyError(note_id)
    body = (note_markdown if note_markdown is not None else n.markdown).strip()
    truncated = len(body) > NOTE_LIMIT
    parts = [f'NOTE TITLE: {n.title}',
             "CURRENT NOTE" + (" (truncated)" if truncated else "") + ":\n" + (body[:NOTE_LIMIT] or "(empty)")]
    if len(body) > WHOLE_NOTE_LIMIT:
        parts.append('(The note is long: do not use "replace_note"; use "insert" or "replace_selection".)')
    if selection.strip():
        parts.append("SELECTED TEXT:\n" + selection.strip()[:4000])
    ctx = mention_context(mentions or [], exclude=n.id)
    if ctx:
        parts.append("MENTIONED NOTES:\n" + ctx)
    hits = []
    if use_book:
        try:
            hits = index.search(build_queries(instruction, []), k=4)
        except Exception as e:
            log.warning("book search failed: %s", e)
    if hits:
        parts.append("BOOK EXCERPTS (use only if relevant):\n" + format_context(hits))
    parts.append("REQUEST: " + instruction.strip())

    data = llm.chat_json(ASSIST_SYSTEM, "\n\n".join(parts), temperature=0.3)
    action = data.get("action") if data.get("action") in ("insert", "replace_selection", "replace_note", "reply") else "insert"
    if action == "replace_selection" and not selection.strip():
        action = "insert"
    if action == "replace_note" and len(body) > WHOLE_NOTE_LIMIT:
        action = "insert"
    content = str(data.get("content") or "").strip()
    content = re.sub(r"\s*\[\d+(?:,\s*\d+)*\]", "", content) if action != "reply" else content
    used_book = bool(data.get("used_book")) and bool(hits)
    sources, seen = [], set()
    for c in json.loads(citations_json(hits)) if used_book else []:
        key = (c.get("document_id"), c.get("page"))
        if key not in seen:
            seen.add(key)
            sources.append(c)
    refs = r"\[\d+\](?:\s*(?:and|,)\s*\[\d+\])*"
    message = re.sub(r"(?:the\s+)?book\s+excerpts?\s*" + refs, "your book", str(data.get("message") or ""))
    message = re.sub(r"\s*(?:excerpts?\s*)?" + refs, "", message)
    return {"action": action, "content": content, "message": message.strip(), "used_book": used_book,
            "sources": sources}
