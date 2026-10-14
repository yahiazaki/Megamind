"""First-time setup: register the translated notes + supplements, ingest them, build the book, seed the profile.

  python scripts/bootstrap.py              # ingest documents that are not ready yet
  python scripts/bootstrap.py --reingest   # re-process everything
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlmodel import select  # noqa: E402

from app.config import ROOT as REPO, get_settings  # noqa: E402
from app.db import init_db, session_scope  # noqa: E402
from app.ingest import book, pipeline  # noqa: E402
from app.models import Document, Profile  # noqa: E402
from app.rag.index import index  # noqa: E402

NOTES = [
    ("01-security", "Security", "Security"),
    ("02-networks", "Computer & Network Fundamentals", "Networks"),
    ("03-bash", "Bash Scripting", "Bash"),
    ("04-apis", "APIs & HTTP Requests", "APIs"),
    ("05-databases", "Databases & SQL", "Databases"),
    ("06-python", "Python", "Python"),
    ("07-design-patterns", "Design Patterns", "Design Patterns"),
    ("08-embedded", "Embedded Systems & RTOS", "Embedded"),
]


def register() -> list[int]:
    s_ = get_settings()
    ids = []
    with session_scope() as s:
        existing = {d.source_path: d for d in s.exec(select(Document)).all()}
        for i, (slug, title, subject) in enumerate(NOTES, start=1):
            translated = s_.data_dir / "translated" / f"{slug}.docx"
            original = s_.data_dir / "sources" / f"{slug}.docx"
            src = translated if translated.exists() else original
            if not src.exists():
                print(f"  ! missing {slug}, skipped")
                continue
            d = existing.get(str(src)) or Document(title=title, subject=subject, kind="note", source_path=str(src),
                                                   translate=False, sort_order=i * 10)
            s.add(d)
            supp = next((REPO / "knowledge" / "supplements").glob(f"{slug[:2]}-*.md"), None)
            if supp:
                sd = existing.get(str(supp)) or Document(title=f"{title} — Supplement", subject=subject,
                                                         kind="supplement", source_path=str(supp), translate=False,
                                                         sort_order=i * 10 + 5)
                s.add(sd)
        s.commit()
        ids = [d.id for d in s.exec(select(Document).order_by(Document.sort_order)).all()]
    return ids


def seed_profile():
    src = get_settings().data_dir / "profile.json"
    with session_scope() as s:
        row = s.get(Profile, 1)
        if (row is None or row.data in ("", "{}")) and src.exists():
            s.add(Profile(id=1, data=src.read_text(encoding="utf-8")))
            s.commit()
            print("  profile seeded from data/profile.json")


def main():
    reingest = "--reingest" in sys.argv
    init_db()
    seed_profile()
    ids = register()
    with session_scope() as s:
        docs = [s.get(Document, i) for i in ids]
        todo = [(d.id, d.title) for d in docs if reingest or d.status != "ready"]
    print(f"{len(ids)} documents registered, {len(todo)} to ingest")
    for doc_id, title in todo:
        t = time.time()
        print(f"  -> {title} …", end="", flush=True)
        pipeline.ingest_document(doc_id, None, rebuild=False)
        with session_scope() as s:
            d = s.get(Document, doc_id)
            print(f" {d.status} ({d.page_count} pages, {time.time() - t:.0f}s) {d.error}")
    print("building the book …")
    out = book.build_book()
    index.reload()
    print(f"done: {out}  |  index: {index.stats()}")
    print(json.dumps({"book": str(out)}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
