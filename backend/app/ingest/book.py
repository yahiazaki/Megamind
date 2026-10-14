"""Assemble every ready document into one book PDF (cover, contents, chapters, bookmarks, page numbers)."""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import pymupdf
from sqlmodel import select

from ..config import ROOT, get_settings
from ..db import session_scope
from ..models import Document

A4 = pymupdf.paper_rect("a4")
BLUE = (0.07, 0.36, 0.85)
NAVY = (0.03, 0.15, 0.4)
GREY = (0.45, 0.45, 0.5)
LOGO = ROOT / "frontend" / "public" / "megamind-logo.svg"
TOC_LINES_PER_PAGE = 28


def book_path() -> Path:
    return get_settings().data_dir / "book" / "Megamind_Book.pdf"


def _cover(book: pymupdf.Document, n_docs: int, n_pages: int):
    page = book.new_page(width=A4.width, height=A4.height)
    page.draw_rect(pymupdf.Rect(0, 0, A4.width, 260), color=None, fill=(0.93, 0.96, 1.0))
    if LOGO.exists():
        try:
            svg = pymupdf.open(str(LOGO))
            pdf = pymupdf.open("pdf", svg.convert_to_pdf())
            page.show_pdf_page(pymupdf.Rect(A4.width / 2 - 80, 60, A4.width / 2 + 80, 220), pdf, 0)
        except Exception:
            pass
    page.insert_textbox(pymupdf.Rect(40, 290, A4.width - 40, 360), "MEGAMIND", fontsize=40, fontname="hebo",
                        color=BLUE, align=1)
    page.insert_textbox(pymupdf.Rect(40, 365, A4.width - 40, 400), "The Knowledge Book of Yahia Zaki", fontsize=18,
                        fontname="helv", color=NAVY, align=1)
    page.insert_textbox(pymupdf.Rect(60, 430, A4.width - 60, 520),
                        "Five years of study notes on security, networking, software engineering and embedded "
                        "systems, translated to English and extended with supplementary chapters.",
                        fontsize=11, fontname="helv", color=GREY, align=1)
    page.insert_textbox(pymupdf.Rect(40, A4.height - 90, A4.width - 40, A4.height - 50),
                        f"{n_docs} chapters  ·  {n_pages} pages  ·  built {datetime.now():%d %B %Y}",
                        fontsize=10, fontname="helv", color=GREY, align=1)


def _toc_pages(book: pymupdf.Document, entries: list[tuple[str, int, str]], n_pages: int):
    """entries: (title, start_page, kind). Returns list of (page_index, rect, target_page) for links."""
    links = []
    for p in range(n_pages):
        page = book.new_page(width=A4.width, height=A4.height)
        if p == 0:
            page.insert_text((50, 80), "Contents", fontsize=26, fontname="hebo", color=BLUE)
        y = 120 if p == 0 else 70
        for title, start, kind in entries[p * TOC_LINES_PER_PAGE:(p + 1) * TOC_LINES_PER_PAGE]:
            indent = 70 if kind == "supplement" else 50
            size = 10.5 if kind == "supplement" else 12.5
            font = "helv" if kind == "supplement" else "hebo"
            color = GREY if kind == "supplement" else NAVY
            label = title.replace("—", "-")[:80]
            page.insert_text((indent, y), label, fontsize=size, fontname=font, color=color)
            page.insert_text((A4.width - 80, y), str(start), fontsize=size, fontname="helv", color=color)
            page.draw_line((indent + 4 + pymupdf.get_text_length(label, font, size), y - 3),
                           (A4.width - 88, y - 3), color=(0.85, 0.85, 0.88), width=0.5, dashes="[1 3] 0")
            links.append((book.page_count - 1, pymupdf.Rect(indent, y - size, A4.width - 50, y + 4), start))
            y += 24
    return links


def build_book() -> Path:
    with session_scope() as s:
        docs = s.exec(select(Document).where(Document.status == "ready").order_by(Document.sort_order)).all()
        docs = [d for d in docs if d.pdf_path and Path(d.pdf_path).exists()]
        sources = [(d.id, d.title, d.kind, pymupdf.open(d.pdf_path)) for d in docs]

    toc_pages = max(1, math.ceil(len(sources) / TOC_LINES_PER_PAGE))
    start = 1 + toc_pages + 1
    entries, starts = [], {}
    for doc_id, title, kind, pdf in sources:
        starts[doc_id] = start
        entries.append((title, start, kind))
        start += pdf.page_count
    total = start - 1

    book = pymupdf.open()
    _cover(book, len(sources), total)
    links = _toc_pages(book, entries, toc_pages)
    toc = [[1, "Cover", 1], [1, "Contents", 2]]
    for doc_id, title, kind, pdf in sources:
        book.insert_pdf(pdf)
        toc.append([1, title, starts[doc_id]])
        for level, sub, page, *_ in pdf.get_toc(simple=True):
            if page >= 1:
                sub = sub if len(sub) <= 90 else sub[:87].rstrip() + "..."
                toc.append([min(level + 1, toc[-1][0] + 1), sub, page + starts[doc_id] - 1])
        pdf.close()

    for page_index, rect, target in links:
        book[page_index].insert_link({"kind": pymupdf.LINK_GOTO, "from": rect, "page": target - 1})
    for i in range(1, book.page_count):
        page = book[i]
        r = page.rect
        page.insert_textbox(pymupdf.Rect(0, r.height - 28, r.width, r.height - 12), f"Megamind  ·  {i + 1}",
                            fontsize=8, fontname="helv", color=GREY, align=1)
    book.set_toc(toc, collapse=1)
    book.set_metadata({"title": "Megamind — The Knowledge Book of Yahia Zaki", "author": "Yahia Zaki",
                       "creator": "Megamind"})

    out = book_path()
    tmp = out.with_suffix(".tmp.pdf")
    book.save(str(tmp), garbage=3, deflate=True)
    book.close()
    tmp.replace(out)

    with session_scope() as s:
        for d in s.exec(select(Document)).all():
            d.book_start_page = starts.get(d.id)
            s.add(d)
        s.commit()
    return out
