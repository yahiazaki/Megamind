"""Build the rewritten book from data/book_src/outline.json.

Usage:
  python scripts/book_build.py                 # register/refresh chapters, ingest changed ones, rebuild the book
  python scripts/book_build.py --replace-old   # also archive the original note/supplement documents
  python scripts/book_build.py --only ch05     # re-ingest only chapters whose file name starts with ch05

outline.json: {"parts": [{"title": "Networking", "chapters": [{"file": "ch04-how-networks-work.md",
                                                               "title": "How Networks Work"}]}]}
Archived documents keep their files and can be restored by setting their status back to "ready" and re-ingesting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlmodel import delete, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_setting, init_db, session_scope, set_setting  # noqa: E402
from app.ingest import book, pipeline  # noqa: E402
from app.models import Chunk, Document  # noqa: E402


def _digest(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:16]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replace-old", action="store_true", help="archive original note/supplement documents")
    ap.add_argument("--only", default="", help="re-ingest chapters whose file starts with this prefix")
    ap.add_argument("--force", action="store_true", help="re-ingest every chapter even if unchanged")
    args = ap.parse_args()

    init_db()
    src_dir = get_settings().data_dir / "book_src"
    outline = json.loads((src_dir / "outline.json").read_text(encoding="utf-8"))

    if args.replace_old:
        with session_scope() as s:
            old = s.exec(select(Document).where(Document.kind.in_(["note", "supplement"]))).all()
            for d in old:
                s.exec(delete(Chunk).where(Chunk.document_id == d.id))
                d.status, d.error = "archived", "Replaced by the rewritten book"
                s.add(d)
            s.commit()
            print(f"archived {len(old)} original documents")

    todo: list[tuple[int, str]] = []
    for pi, part in enumerate(outline["parts"], 1):
        for ci, ch in enumerate(part["chapters"], 1):
            path = src_dir / ch["file"]
            if not path.exists():
                print(f"  skip (missing): {ch['file']}")
                continue
            order = pi * 100 + ci
            with session_scope() as s:
                doc = s.exec(select(Document).where(Document.source_path == str(path))).first()
                if doc is None:
                    doc = Document(title=ch["title"], subject=part["title"], kind="chapter", source_path=str(path),
                                   translate=False, polish=False)
                doc.title, doc.subject, doc.sort_order = ch["title"], part["title"], order
                s.add(doc)
                s.commit()
                s.refresh(doc)
                doc_id, status = doc.id, doc.status
            key = f"book_digest_{doc_id}"
            digest = _digest(path)
            changed = digest != get_setting(key) or status != "ready"
            if args.force or (args.only and ch["file"].startswith(args.only)) or (not args.only and changed):
                todo.append((doc_id, ch["file"]))
                set_setting(key, digest)

    # workspace notes and uploads stay in their parts; parts not in the outline go after the book's parts
    titles = [p["title"] for p in outline["parts"]]
    with session_scope() as s:
        for d in s.exec(select(Document).where(Document.kind.notin_(["chapter", "note", "supplement"]))).all():
            if d.subject in titles:
                base = (titles.index(d.subject) + 1) * 100
                if not base + 50 <= d.sort_order < base + 100:
                    d.sort_order = base + 50 + (d.id % 49)
            elif d.sort_order < 10_000:
                d.sort_order = 10_000 + d.id
            s.add(d)
        s.commit()

    for i, (doc_id, name) in enumerate(todo, 1):
        t = time.time()
        pipeline.ingest_document(doc_id, rebuild=False)
        with session_scope() as s:
            d = s.get(Document, doc_id)
            print(f"[{i}/{len(todo)}] {name}: {d.status} {d.page_count} pages ({time.time() - t:.0f}s) {d.error[:200]}")
            if d.status != "ready":
                set_setting(f"book_digest_{doc_id}", "")
    out = book.build_book()
    from app.rag.index import index
    index.reload()
    print("book:", out)


if __name__ == "__main__":
    main()
