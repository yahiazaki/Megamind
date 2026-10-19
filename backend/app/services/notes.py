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

log = logging.getLogger(__name__)

NOTE_LIMIT = 12000      # characters of the open note sent to the model
MENTION_LIMIT = 3000    # characters per @mentioned note
WHOLE_NOTE_LIMIT = 10000  # longer notes are never rewritten in one go (the model would drop content)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def summary(n: Note) -> dict:
    return {"id": n.id, "title": n.title, "updated_at": n.updated_at.isoformat(), "in_book": bool(n.document_id),
            "book_part": n.book_part, "book_mode": n.book_mode or ("chapter" if n.document_id else ""),
            "published_at": n.published_at.isoformat() if n.published_at else None,
            "stale": bool(n.published_at and n.updated_at > n.published_at)}


def full(n: Note) -> dict:
    d = summary(n) | {"html": n.html, "markdown": n.markdown}
    if n.document_id:
        with session_scope() as s:
            doc = s.get(Document, n.document_id)
            if doc:
                d |= {"document_status": doc.status, "book_page": doc.book_start_page, "document_error": doc.error,
                      "book_chapter": doc.title}
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
    if remove_from_book:
        unpublish(note_id)   # removes its chapter, or its section from the chapter it was added to
    with session_scope() as s:
        n = s.get(Note, note_id)
        if n:
            s.delete(n)
            s.commit()


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

SECTION_START = "<!-- megamind-note:{id} -->"
SECTION_END = "<!-- /megamind-note:{id} -->"
TEXT_SOURCES = (".md", ".markdown", ".txt")


def book_structure() -> list[dict]:
    """Parts of the book in order, each with its chapters; can_insert marks chapters a note can be appended into."""
    with session_scope() as s:
        docs = s.exec(select(Document).where(Document.status.notin_(["archived", "error"]))
                      .order_by(Document.sort_order)).all()
        parts: dict[str, list[dict]] = {}
        for d in docs:
            parts.setdefault(d.subject or "Notes", []).append({
                "id": d.id, "title": d.title,
                "can_insert": d.kind != "workspace" and d.source_path.lower().endswith(TEXT_SOURCES)})
    return [{"part": p, "chapters": c} for p, c in parts.items()]


def book_parts() -> list[str]:
    return [p["part"] for p in book_structure()]


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


def _blocks(markdown: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", markdown or "") if b.strip()]


def new_blocks(published: str, current: str) -> str:
    """Paragraphs, lists and headings in the current note that were not in the published version."""
    import difflib

    old, new = _blocks(published), _blocks(current)

    def norm(b: str) -> str:
        return re.sub(r"\s+", " ", b).lower()

    sm = difflib.SequenceMatcher(a=[norm(b) for b in old], b=[norm(b) for b in new], autojunk=False)
    added = []
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            added.extend(new[j1:j2])
    return "\n\n".join(added)


def _demote(markdown: str) -> str:
    """Note headings become sub-headings of the note's own '## title' section inside a chapter."""
    def fix(m):
        return "#" * min(max(len(m.group(1)) + 1, 3), 4) + " "
    return re.sub(r"(?m)^(#{1,6})\s+", fix, markdown)


def _strip_title(markdown: str, title: str) -> str:
    """Drop a leading heading that just repeats the note's title (the section already has it)."""
    text = markdown.strip()
    m = re.match(r"#{1,6}\s+(.+)\n*", text)
    if m and m.group(1).strip().lower() == title.strip().lower():
        text = text[m.end():].lstrip()
    return text


def _write_section(chapter: Path, note_id: int, title: str, body: str, update: str) -> None:
    """Insert or update the note's section in a chapter, after the chapter's last section (before Key Takeaways)."""
    src = chapter.read_text(encoding="utf-8")
    start, end = SECTION_START.format(id=note_id), SECTION_END.format(id=note_id)
    block_re = re.compile(re.escape(start) + r"(.*?)" + re.escape(end), re.S)
    body = _demote(_strip_title(body, title))
    m = block_re.search(src)
    if m and update == "append":
        src = src[:m.start(1)] + m.group(1).rstrip() + "\n\n" + body + "\n" + src[m.end(1):]
    elif m:
        src = src[:m.start(1)] + f"\n## {title}\n\n{body}\n" + src[m.end(1):]
    else:
        block = f"{start}\n## {title}\n\n{body}\n{end}\n"
        takeaways = re.search(r"(?m)^## Key Takeaways\s*$", src)
        if takeaways:
            src = src[:takeaways.start()] + block + "\n" + src[takeaways.start():]
        else:
            src = src.rstrip() + "\n\n" + block
    chapter.write_text(src, encoding="utf-8")


def _remove_section(chapter: Path, note_id: int) -> None:
    if not chapter.exists():
        return
    src = chapter.read_text(encoding="utf-8")
    start, end = SECTION_START.format(id=note_id), SECTION_END.format(id=note_id)
    src = re.sub(re.escape(start) + r".*?" + re.escape(end) + r"\n?", "", src, flags=re.S)
    chapter.write_text(src, encoding="utf-8")


def publish(note_id: int, part: str, polish: bool = False, mode: str = "chapter", chapter_id: int | None = None,
            update: str = "replace") -> dict:
    """Add the note to the book (or update it there) in the background.

    mode    "chapter": the note becomes its own chapter at the end of `part`.
            "section": the note is appended inside chapter `chapter_id`, after its last section.
    update  "replace": the book gets the whole current note.  "append": only what is new since the last publish.
    A note that is already in the book stays where it is; remove it from the book to move it.
    """
    from ..ingest.pipeline import _executor
    from ..models import Job

    n = get(note_id)
    if not n:
        raise KeyError(note_id)
    current = n.markdown.strip()
    if not current:
        raise ValueError("The note is empty")
    in_book = bool(n.document_id)
    if in_book:
        mode = n.book_mode or "chapter"
        chapter_id = n.document_id if mode == "section" else None
        part = n.book_part or part
    part = (part or "").strip() or "Notes"
    if update == "append" and in_book:
        payload = new_blocks(n.published_markdown, current)
        if not payload:
            raise ValueError("Nothing new has been added since this note was last put in the book")
    else:
        update, payload = "replace", current

    with session_scope() as s:
        if mode == "section":
            doc = s.get(Document, chapter_id) if chapter_id else None
            if doc is None or not doc.source_path.lower().endswith(TEXT_SOURCES):
                raise ValueError("Choose a chapter of the book to add the note into")
            part = doc.subject
        else:
            src = get_settings().data_dir / "notes" / f"note-{n.id}.md"
            doc = s.get(Document, n.document_id) if in_book else None
            if doc is None:
                doc = Document(title=n.title, subject=part, kind="workspace", source_path=str(src), translate=False)
            doc.title, doc.subject, doc.source_path = n.title, part, str(src)
            doc.sort_order = _sort_order_for(part, doc.id)
        doc.status, doc.error, doc.polish = "pending", "", False
        s.add(doc)
        s.commit()
        s.refresh(doc)
        doc_id = doc.id
        job = Job(kind="publish-note", document_id=doc_id)
        s.add(job)
        note = s.get(Note, n.id)
        note.document_id, note.book_part, note.book_mode = doc_id, part, mode
        s.add(note)
        s.commit()
        s.refresh(job)
        job_id = job.id

    _executor.submit(_run_publish, n.id, n.title, doc_id, mode, payload, current, update, polish, job_id)
    return {"document_id": doc_id, "job_id": job_id, "mode": mode, "update": update}


def _run_publish(note_id: int, title: str, doc_id: int, mode: str, payload: str, snapshot: str, update: str,
                 polish: bool, job_id: int) -> None:
    from ..ingest import pipeline, restructure

    try:
        text = payload
        if polish:
            def progress(done, total):
                pipeline._job_update(job_id, status="running", progress=0.05 + 0.4 * done / max(total, 1),
                                     message=f"Rewriting into book style: section {done}/{total}")
            text = restructure.polish_markdown(f"# {title}\n\n{payload}", title, llm.chat_json, progress)
            text = re.sub(r"^#\s+.*\n+", "", text.strip(), count=1)
        with session_scope() as s:
            target = Path(s.get(Document, doc_id).source_path)
        if mode == "section":
            _write_section(target, note_id, title, text, update)
        else:
            if update == "append" and target.exists():
                body = target.read_text(encoding="utf-8").rstrip() + "\n\n" + text.strip() + "\n"
            else:
                body = f"# {title}\n\n{text.strip()}\n"
            target.write_text(body, encoding="utf-8")
        pipeline.ingest_document(doc_id, job_id)
        with session_scope() as s:
            note = s.get(Note, note_id)
            if note:
                note.published_markdown, note.published_at = snapshot, datetime.now()
                s.add(note)
                s.commit()
    except Exception as e:
        log.exception("publishing note %s failed", note_id)
        pipeline._job_update(job_id, status="error", message=str(e)[:500])
        pipeline._doc_update(doc_id, status="error", error=str(e)[:500])


def unpublish(note_id: int) -> None:
    from ..ingest.pipeline import delete_document, queue_ingest

    chapter = None
    with session_scope() as s:
        n = s.get(Note, note_id)
        if not n or not n.document_id:
            return
        doc_id, mode = n.document_id, n.book_mode or "chapter"
        n.document_id, n.book_part, n.book_mode, n.published_at, n.published_markdown = None, "", "", None, ""
        s.add(n)
        s.commit()
        doc = s.get(Document, doc_id)
        if mode == "section" and doc:
            chapter = Path(doc.source_path)
    if mode == "section":
        if chapter:
            _remove_section(chapter, note_id)
            queue_ingest(doc_id)
    else:
        delete_document(doc_id)


# ---------------------------------------------------------------------------
# AI writing assistant (the model's own knowledge — no book search)
# ---------------------------------------------------------------------------

ASSIST_SYSTEM = """You are Megamind's writing assistant inside Yahia's notes editor. You write from your own knowledge;
you do not search any book. Return JSON:
{"action": "rewrite_note" | "replace_selection" | "insert" | "reply",
 "content": "markdown",
 "added": "markdown: only the new material you added (empty for reply)",
 "message": "one short sentence saying what you changed"}

Actions:
- "rewrite_note" is the default whenever he asks to add, write, explain, expand, include, reorganise or clean up.
  Integrate what he asked for into the note and rewrite the WHOLE note your own way: put it in a logical order with
  clear ## and ### headings, merge duplicates and improve the wording. Keep EVERY fact, example, command and code
  block already in the note. content = the complete new note; added = only the new material.
- "replace_selection": he selected text (SELECTED TEXT is given) and asks to change only that part (rewrite, fix,
  shorten, translate, turn into a table). content = the replacement for exactly that selection.
- "insert": only when you are told the note is too long to rewrite. content = only the new material.
- "reply": he asks a question and does not want the note changed. content = the answer.

MENTIONED NOTES are his other pages; use them when he refers to them.
Style: English, clean markdown (## headings, - bullets, **bold**, `code`, tables when useful), accurate and concise.
Do not repeat the note's title as a heading."""

MIN_KEPT = 0.8   # share of the note's key terms a full rewrite must keep, otherwise only the new part is proposed


def assist(note_id: int, instruction: str, selection: str = "", mentions: list[int] | None = None,
           use_book: bool = False, note_markdown: str | None = None) -> dict:
    from ..ingest.restructure import coverage

    n = get(note_id)
    if not n:
        raise KeyError(note_id)
    body = (note_markdown if note_markdown is not None else n.markdown).strip()
    too_long = len(body) > WHOLE_NOTE_LIMIT
    parts = [f"NOTE TITLE: {n.title}",
             "CURRENT NOTE" + (" (truncated)" if len(body) > NOTE_LIMIT else "") + ":\n" + (body[:NOTE_LIMIT] or "(empty)")]
    if too_long:
        parts.append('(The note is too long to rewrite in one go: use "insert" or "replace_selection".)')
    if selection.strip():
        parts.append("SELECTED TEXT:\n" + selection.strip()[:4000])
    ctx = mention_context(mentions or [], exclude=n.id)
    if ctx:
        parts.append("MENTIONED NOTES:\n" + ctx)
    parts.append("REQUEST: " + instruction.strip())

    data = llm.chat_json(ASSIST_SYSTEM, "\n\n".join(parts), temperature=0.3)
    action = str(data.get("action") or "")
    content = str(data.get("content") or "").strip()
    added = str(data.get("added") or "").strip()
    message = str(data.get("message") or "").strip()

    if action == "replace_selection" and not selection.strip():
        action = "rewrite_note"
    if action not in ("rewrite_note", "replace_selection", "insert", "reply"):
        action = "rewrite_note"
    if action == "rewrite_note":
        if too_long:
            action, content = "insert", added or content
        elif body and coverage(body, content) < MIN_KEPT:
            # the rewrite lost part of the existing note: offer only the new material instead
            action, content = "insert", added
            message = "The full rewrite would have dropped some of your existing text, so only the new part is proposed."
        else:
            action = "replace_note"
    if action == "insert" and not content:
        content = added
    if action != "reply":
        content = _strip_title(content, n.title)
    return {"action": action, "content": content, "message": message, "used_book": False, "sources": []}
