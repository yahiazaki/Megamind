"""Admin library: documents, uploads, ingestion jobs, the book and page previews."""
import json
import re
from datetime import datetime
from pathlib import Path

import pymupdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import select

from ..config import get_settings
from ..db import session_scope
from ..ingest import book, convert, pipeline
from ..models import Chunk, Document, Job
from ..rag.index import build_queries, index
from ..security import require_admin

router = APIRouter(prefix="/api/library", dependencies=[Depends(require_admin)])


class TextNoteIn(BaseModel):
    title: str
    subject: str = ""
    content: str
    translate: bool = True


class DocPatch(BaseModel):
    title: str | None = None
    subject: str | None = None
    sort_order: float | None = None


def _doc_dict(d: Document, chunks: int = 0) -> dict:
    return {"id": d.id, "title": d.title, "subject": d.subject, "kind": d.kind, "status": d.status, "error": d.error,
            "pages": d.page_count, "book_start_page": d.book_start_page, "sort_order": d.sort_order,
            "chunks": chunks, "file": Path(d.source_path).name, "created_at": d.created_at}


def _next_sort_order(subject: str) -> float:
    with session_scope() as s:
        docs = s.exec(select(Document).order_by(Document.sort_order)).all()
    same = [d.sort_order for d in docs if subject and d.subject.lower() == subject.lower()]
    if same:
        after = max(same)
        later = [d.sort_order for d in docs if d.sort_order > after]
        return (after + min(later)) / 2 if later else after + 1
    return (max((d.sort_order for d in docs), default=0) // 10 + 1) * 10


def _create_and_queue(path: Path, title: str, subject: str, translate: bool) -> dict:
    with session_scope() as s:
        d = Document(title=title, subject=subject, kind="upload", source_path=str(path), translate=translate,
                     sort_order=_next_sort_order(subject))
        s.add(d)
        s.commit()
        s.refresh(d)
        doc = _doc_dict(d)
    job_id = pipeline.queue_ingest(doc["id"])
    return {"document": doc, "job_id": job_id}


@router.get("/documents")
def documents():
    with session_scope() as s:
        counts = dict(s.exec(select(Chunk.document_id, func.count(Chunk.id)).group_by(Chunk.document_id)).all())
        docs = s.exec(select(Document).order_by(Document.sort_order)).all()
        return [_doc_dict(d, counts.get(d.id, 0)) for d in docs]


@router.get("/subjects")
def subjects():
    with session_scope() as s:
        return sorted({d.subject for d in s.exec(select(Document)).all() if d.subject})


@router.post("/upload")
async def upload(file: UploadFile = File(...), title: str = Form(""), subject: str = Form(""),
                 translate: bool = Form(True)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in convert.SUPPORTED:
        raise HTTPException(400, f"Unsupported file type {ext}. Use: {', '.join(sorted(convert.SUPPORTED))}")
    safe = re.sub(r"[^\w.\- ]+", "_", Path(file.filename).name)
    dest = get_settings().data_dir / "uploads" / f"{datetime.now():%Y%m%d-%H%M%S}_{safe}"
    dest.write_bytes(await file.read())
    return _create_and_queue(dest, title.strip() or Path(safe).stem, subject.strip(), translate)


@router.post("/text")
def add_text(body: TextNoteIn):
    safe = re.sub(r"[^\w\-]+", "_", body.title)[:50] or "note"
    dest = get_settings().data_dir / "uploads" / f"{datetime.now():%Y%m%d-%H%M%S}_{safe}.md"
    dest.write_text(body.content, encoding="utf-8")
    return _create_and_queue(dest, body.title.strip(), body.subject.strip(), body.translate)


@router.patch("/documents/{doc_id}")
def patch_document(doc_id: int, body: DocPatch):
    with session_scope() as s:
        d = s.get(Document, doc_id)
        if not d:
            raise HTTPException(404)
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(d, k, v)
        s.add(d)
        s.commit()
    return {"job_id": pipeline.queue_rebuild_book()}


@router.post("/documents/{doc_id}/reingest")
def reingest(doc_id: int):
    return {"job_id": pipeline.queue_ingest(doc_id)}


@router.delete("/documents/{doc_id}")
def delete(doc_id: int):
    pipeline.delete_document(doc_id)
    return {"ok": True}


@router.post("/rebuild")
def rebuild():
    return {"job_id": pipeline.queue_rebuild_book()}


@router.get("/jobs")
def jobs(limit: int = 20):
    with session_scope() as s:
        rows = s.exec(select(Job).order_by(Job.id.desc()).limit(limit)).all()
        return [r.model_dump() for r in rows]


@router.get("/book.pdf")
def book_pdf():
    p = book.book_path()
    if not p.exists():
        raise HTTPException(404, "The book has not been built yet")
    return FileResponse(p, media_type="application/pdf", filename="Megamind_Book.pdf",
                        content_disposition_type="inline")


@router.get("/documents/{doc_id}/pdf")
def document_pdf(doc_id: int):
    with session_scope() as s:
        d = s.get(Document, doc_id)
    if not d or not d.pdf_path or not Path(d.pdf_path).exists():
        raise HTTPException(404)
    return FileResponse(d.pdf_path, media_type="application/pdf", content_disposition_type="inline")


@router.get("/chunks/{chunk_id}")
def chunk(chunk_id: int):
    with session_scope() as s:
        c = s.get(Chunk, chunk_id)
        if not c:
            raise HTTPException(404)
        d = s.get(Document, c.document_id)
        return {"id": c.id, "document_id": d.id, "doc_title": d.title, "section": c.section, "page": c.page,
                "book_page": (d.book_start_page + c.page - 1) if d.book_start_page else None, "text": c.text}


@router.get("/page.png")
def page_png(doc_id: int, page: int, chunk_id: int | None = None, zoom: float = 1.6):
    with session_scope() as s:
        d = s.get(Document, doc_id)
        c = s.get(Chunk, chunk_id) if chunk_id else None
    if not d or not d.pdf_path:
        raise HTTPException(404)
    with pymupdf.open(d.pdf_path) as pdf:
        if not 1 <= page <= len(pdf):
            raise HTTPException(404)
        pg = pdf[page - 1]
        if c and c.document_id == doc_id:
            for r in json.loads(c.rects or "[]"):
                annot = pg.add_highlight_annot(pymupdf.Rect(r))
                annot.set_colors(stroke=(1.0, 0.86, 0.2))
                annot.update(opacity=0.45)
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(min(zoom, 3), min(zoom, 3)), annots=True)
        return Response(pix.tobytes("png"), media_type="image/png")


@router.get("/search")
def search(q: str, k: int = 8):
    hits = index.search(build_queries(q, []), k=k)
    return [h.citation() | {"score": h.score} for h in hits]


@router.get("/stats")
def stats():
    p = book.book_path()
    return index.stats() | {"book_exists": p.exists(), "book_updated": datetime.fromtimestamp(p.stat().st_mtime)
                            if p.exists() else None}
