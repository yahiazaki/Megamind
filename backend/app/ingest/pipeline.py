"""Ingestion jobs: source file -> (translated) .docx -> PDF -> chunks + embeddings -> book."""
from __future__ import annotations

import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pymupdf
from sqlmodel import delete, select

from .. import llm
from ..config import get_settings
from ..db import session_scope
from ..models import Chunk, Document, Job
from . import book, chunk, convert, translate
from .detect import needs_translation

log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")


def _job_update(job_id: int | None, **fields):
    if job_id is None:
        return
    with session_scope() as s:
        job = s.get(Job, job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_at = datetime.now()
        s.add(job)
        s.commit()


def _doc_update(doc_id: int, **fields):
    with session_scope() as s:
        d = s.get(Document, doc_id)
        for k, v in fields.items():
            setattr(d, k, v)
        s.add(d)
        s.commit()


def _pdf_needs_translation(pdf: Path) -> bool:
    with pymupdf.open(str(pdf)) as doc:
        text = "\n".join(doc[i].get_text() for i in range(min(len(doc), 15)))
    paras = [p for p in text.split("\n\n") if len(p) > 40]
    flagged = sum(1 for p in paras if needs_translation(p))
    return bool(paras) and flagged / len(paras) > 0.1


def ingest_document(doc_id: int, job_id: int | None = None, rebuild: bool = True) -> None:
    s_ = get_settings()
    with session_scope() as s:
        doc = s.get(Document, doc_id)
        src, title, do_translate = Path(doc.source_path), doc.title, doc.translate
    _doc_update(doc_id, status="processing", error="")
    _job_update(job_id, status="running", message="Preparing document", progress=0.02)
    try:
        ext = src.suffix.lower()
        work = src
        tmp = s_.data_dir / "tmp"

        if ext in convert.TEXT_EXTS:
            work = convert.markdown_to_docx(src.read_text(encoding="utf-8", errors="replace"),
                                            tmp / f"{doc_id}.docx", title=title)
        elif ext == ".pdf" and do_translate and _pdf_needs_translation(src):
            _job_update(job_id, message="Reflowing PDF into an editable document", progress=0.05)
            try:
                work = convert.to_docx(src, tmp / f"{doc_id}.docx")
            except Exception as e:
                log.warning("PDF reflow failed, keeping original PDF: %s", e)
        elif ext in {".doc", ".rtf", ".odt"}:
            work = convert.to_docx(src, tmp / f"{doc_id}.docx")

        if work.suffix.lower() == ".docx" and do_translate:
            items = translate.extract(work)
            if items:
                _job_update(job_id, message=f"Translating {len(items)} paragraphs to English", progress=0.1)

                def progress(done, total):
                    _job_update(job_id, progress=0.1 + 0.45 * done / total,
                                message=f"Translating paragraphs {done}/{total}")

                tr = translate.translate_items(items, llm.chat_json, progress)
                translated = s_.data_dir / "translated" / f"{doc_id}.docx"
                translate.apply(work, translated, tr)
                work = translated

        pdf_out = s_.data_dir / "pdf" / f"{doc_id}.pdf"
        _job_update(job_id, message="Converting to PDF", progress=0.6)
        if work.suffix.lower() == ".pdf":
            pdf_out.write_bytes(work.read_bytes())
        else:
            convert.word_to_pdf(work, pdf_out)

        _job_update(job_id, message="Splitting into passages", progress=0.7)
        chunks, n_pages = chunk.chunk_pdf(pdf_out, title)
        _job_update(job_id, message=f"Embedding {len(chunks)} passages", progress=0.75)
        vecs = llm.embed([f"{title} > {c.section}\n{c.text}" for c in chunks]) if chunks else np.zeros((0, 1))

        with session_scope() as s:
            s.exec(delete(Chunk).where(Chunk.document_id == doc_id))
            for c, v in zip(chunks, vecs):
                s.add(Chunk(document_id=doc_id, page=c.page, section=c.section, text=c.text,
                            rects=json.dumps(c.rects), embedding=v.astype(np.float32).tobytes()))
            d = s.get(Document, doc_id)
            d.pdf_path, d.page_count, d.status = str(pdf_out), n_pages, "ready"
            s.add(d)
            s.commit()

        if rebuild:
            _job_update(job_id, message="Rebuilding the book", progress=0.92)
            book.build_book()
        from ..rag.index import index
        index.reload()
        _job_update(job_id, status="done", progress=1.0, message=f"Ready: {n_pages} pages, {len(chunks)} passages")
    except Exception as e:
        log.error("ingest failed: %s", traceback.format_exc())
        _doc_update(doc_id, status="error", error=str(e)[:500])
        _job_update(job_id, status="error", message=str(e)[:500])


def queue_ingest(doc_id: int) -> int:
    with session_scope() as s:
        job = Job(kind="ingest", document_id=doc_id)
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id
    _executor.submit(ingest_document, doc_id, job_id)
    return job_id


def queue_rebuild_book() -> int:
    with session_scope() as s:
        job = Job(kind="book")
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id

    def run():
        try:
            _job_update(job_id, status="running", message="Rebuilding the book", progress=0.3)
            book.build_book()
            _job_update(job_id, status="done", progress=1.0, message="Book rebuilt")
        except Exception as e:
            _job_update(job_id, status="error", message=str(e)[:500])
    _executor.submit(run)
    return job_id


def delete_document(doc_id: int) -> None:
    with session_scope() as s:
        s.exec(delete(Chunk).where(Chunk.document_id == doc_id))
        d = s.get(Document, doc_id)
        if d:
            for p in (d.pdf_path,):
                if p and Path(p).exists():
                    Path(p).unlink(missing_ok=True)
            s.delete(d)
        s.commit()
    from ..rag.index import index
    index.reload()
    queue_rebuild_book()


def recover_interrupted() -> None:
    """Jobs that were running when the server stopped are marked as failed."""
    with session_scope() as s:
        for job in s.exec(select(Job).where(Job.status.in_(["queued", "running"]))).all():
            job.status, job.message = "error", "Interrupted by a server restart — run it again"
            s.add(job)
        for d in s.exec(select(Document).where(Document.status == "processing")).all():
            d.status, d.error = "error", "Interrupted by a server restart"
            s.add(d)
        s.commit()
