"""In-memory hybrid index over all chunks: dense (bge-m3 cosine) + sparse (BM25), fused with RRF."""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sqlmodel import select

from .. import llm
from ..db import session_scope
from ..ingest.detect import needs_translation
from ..models import Chunk, Document

log = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to in and or is are was be for on with as by it this that at from how what why "
           "which who when does do can i you me my we".split())


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP]


@dataclass
class Hit:
    chunk_id: int
    document_id: int
    doc_title: str
    section: str
    page: int
    book_page: int | None
    text: str
    score: float

    def citation(self) -> dict:
        return {"chunk_id": self.chunk_id, "document_id": self.document_id, "doc_title": self.doc_title,
                "section": self.section, "page": self.page, "book_page": self.book_page,
                "snippet": self.text[:300]}


class HybridIndex:
    def __init__(self):
        self._lock = threading.RLock()
        self.rows: list[dict] = []
        self.matrix = np.zeros((0, 1024), dtype=np.float32)
        self.bm25: BM25Okapi | None = None

    def reload(self) -> None:
        with session_scope() as s:
            docs = {d.id: d for d in s.exec(select(Document).where(Document.status == "ready")).all()}
            chunks = [c for c in s.exec(select(Chunk)).all() if c.document_id in docs and c.embedding]
            rows = [{"id": c.id, "doc": c.document_id, "title": docs[c.document_id].title, "section": c.section,
                     "page": c.page, "start": docs[c.document_id].book_start_page, "text": c.text}
                    for c in chunks]
            vecs = [np.frombuffer(c.embedding, dtype=np.float32) for c in chunks]
        with self._lock:
            self.rows = rows
            self.matrix = np.vstack(vecs) if vecs else np.zeros((0, 1024), dtype=np.float32)
            corpus = [tokenize(f"{r['title']} {r['section']} {r['text']}") for r in rows]
            self.bm25 = BM25Okapi(corpus) if corpus else None
        log.info("index loaded: %d chunks from %d documents", len(rows), len(docs))

    def _hit(self, i: int, score: float) -> Hit:
        r = self.rows[i]
        book_page = r["start"] + r["page"] - 1 if r["start"] else None
        return Hit(r["id"], r["doc"], r["title"], r["section"], r["page"], book_page, r["text"], score)

    def fingerprint(self) -> str:
        """Changes whenever the indexed content changes; used to expire cached answers."""
        with self._lock:
            return f"{len(self.rows)}-{max((r['id'] for r in self.rows), default=0)}"

    def search(self, queries: list[str], k: int = 6, doc_ids: set[int] | None = None) -> list[Hit]:
        return self.search_scored(queries, k, doc_ids)[0]

    def search_scored(self, queries: list[str], k: int = 6,
                      doc_ids: set[int] | None = None) -> tuple[list[Hit], float]:
        """Hybrid search; also returns the best cosine similarity, a measure of whether the book covers the question."""
        with self._lock:
            if not self.rows:
                return [], 0.0
            n = len(self.rows)
            allowed = np.ones(n, dtype=bool)
            if doc_ids:
                allowed = np.array([r["doc"] in doc_ids for r in self.rows])
            fused = np.zeros(n)
            best = 0.0
            qvecs = llm.embed(queries)
            for qi, q in enumerate(queries):
                dense = self.matrix @ qvecs[qi]
                dense[~allowed] = -1
                best = max(best, float(dense.max()))
                for rank, i in enumerate(np.argsort(-dense)[:40]):
                    fused[i] += 1 / (60 + rank)
                if self.bm25:
                    sparse = self.bm25.get_scores(tokenize(q))
                    sparse[~allowed] = -1
                    for rank, i in enumerate(np.argsort(-sparse)[:40]):
                        if sparse[i] > 0:
                            fused[i] += 1 / (60 + rank)
            order = [i for i in np.argsort(-fused) if fused[i] > 0][:k]
            return [self._hit(int(i), float(fused[i])) for i in order], best

    def random_chunks(self, n: int, doc_ids: set[int] | None = None) -> list[Hit]:
        with self._lock:
            idx = [i for i, r in enumerate(self.rows) if not doc_ids or r["doc"] in doc_ids]
            idx = [i for i in idx if len(self.rows[i]["text"]) > 400]
            if not idx:
                return []
            pick = np.random.choice(idx, size=min(n, len(idx)), replace=False)
            return [self._hit(int(i), 0.0) for i in pick]

    def stats(self) -> dict:
        with self._lock:
            return {"chunks": len(self.rows), "documents": len({r["doc"] for r in self.rows})}


index = HybridIndex()

REWRITE_SYSTEM = """You turn a student's message into search queries for their English study notes.
The message may be English, Egyptian Arabic, or Franco-Arabic (Arabic in Latin letters with digits: 3=ع, 2=ء, 7=ح).
Use the conversation for context so follow-ups like "explain more" become standalone.
Return JSON: {"queries": ["<standalone English query>", "<alternative phrasing with key technical terms>"]}"""


def build_queries(message: str, history: list[dict]) -> list[str]:
    """Original message plus English rewrites when the message is not plain English or is a follow-up."""
    recent = [m for m in history if m["role"] in ("user", "assistant")][-4:]
    if not needs_translation(message) and (not recent or len(message.split()) > 6):
        return [message]
    convo = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in recent)
    try:
        data = llm.chat_json(REWRITE_SYSTEM, f"Conversation:\n{convo}\n\nMessage: {message}")
        qs = [q for q in data.get("queries", []) if isinstance(q, str) and q.strip()][:2]
        return [message] + qs
    except Exception as e:
        log.warning("query rewrite failed: %s", e)
        return [message]


def format_context(hits: list[Hit]) -> str:
    parts = []
    for n, h in enumerate(hits, start=1):
        page = f"book page {h.book_page}" if h.book_page else f"page {h.page}"
        parts.append(f"[{n}] {h.doc_title} › {h.section} ({page})\n{h.text}")
    return "\n\n".join(parts)


def citations_json(hits: list[Hit]) -> str:
    return json.dumps([dict(h.citation(), n=i + 1) for i, h in enumerate(hits)])
