"""Assemble every ready document into one book PDF.

Structure: cover → contents → for each part (documents grouped by subject, in sort order): a part title page, then
its chapters. Chapters are numbered through the whole book. Bookmarks nest part → chapter → the chapter's headings.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
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
PALE = (0.93, 0.96, 1.0)
LOGO = ROOT / "frontend" / "public" / "megamind-logo.svg"
TOC_LINES_PER_PAGE = 30
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"]


@dataclass
class Chapter:
    doc_id: int
    number: int
    title: str
    pdf: pymupdf.Document
    start: int = 0


@dataclass
class Part:
    number: int
    title: str
    chapters: list[Chapter]
    start: int = 0


def book_path() -> Path:
    return get_settings().data_dir / "book" / "Megamind_Book.pdf"


def _label(text: str, limit: int = 80) -> str:
    # base-14 fonts lack some typographic characters
    text = text.replace("—", "-").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _roman(n: int) -> str:
    return ROMAN[n - 1] if n <= len(ROMAN) else str(n)


def _cover(book: pymupdf.Document, n_parts: int, n_chapters: int, n_pages: int):
    page = book.new_page(width=A4.width, height=A4.height)
    page.draw_rect(pymupdf.Rect(0, 0, A4.width, 260), color=None, fill=PALE)
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
                        "Computing foundations, networking, cybersecurity, programming, software engineering and "
                        "embedded systems - rewritten from five years of study notes into one structured book.",
                        fontsize=11, fontname="helv", color=GREY, align=1)
    page.insert_textbox(pymupdf.Rect(40, A4.height - 90, A4.width - 40, A4.height - 50),
                        f"{n_parts} parts  ·  {n_chapters} chapters  ·  {n_pages} pages  ·  built {datetime.now():%d %B %Y}",
                        fontsize=10, fontname="helv", color=GREY, align=1)


def _toc_entries(parts: list[Part]) -> list[tuple[str, str, int]]:
    """(kind, label, page) rows: 'part' and 'chapter'."""
    rows = []
    for p in parts:
        rows.append(("part", f"Part {_roman(p.number)}   {p.title}", p.start))
        for c in p.chapters:
            rows.append(("chapter", f"{c.number}   {c.title}", c.start))
    return rows


def _toc_pages(book: pymupdf.Document, rows: list[tuple[str, str, int]], n_pages: int):
    """Returns [(page_index, rect, target_page)] for clickable lines."""
    links = []
    for p in range(n_pages):
        page = book.new_page(width=A4.width, height=A4.height)
        if p == 0:
            page.insert_text((50, 80), "Contents", fontsize=26, fontname="hebo", color=BLUE)
        y = 125 if p == 0 else 70
        for kind, label, target in rows[p * TOC_LINES_PER_PAGE:(p + 1) * TOC_LINES_PER_PAGE]:
            is_part = kind == "part"
            if is_part and y > 130:
                y += 8
            indent, size = (50, 12.5) if is_part else (68, 11)
            font, color = ("hebo", BLUE) if is_part else ("helv", NAVY)
            text = _label(label, 70)
            page.insert_text((indent, y), text, fontsize=size, fontname=font, color=color)
            page.insert_text((A4.width - 80, y), str(target), fontsize=size, fontname="helv", color=color)
            page.draw_line((indent + 6 + pymupdf.get_text_length(text, font, size), y - 3), (A4.width - 88, y - 3),
                           color=(0.85, 0.85, 0.88), width=0.5, dashes="[1 3] 0")
            links.append((book.page_count - 1, pymupdf.Rect(indent, y - size, A4.width - 50, y + 4), target))
            y += 22
    return links


def _part_page(book: pymupdf.Document, part: Part):
    page = book.new_page(width=A4.width, height=A4.height)
    page.draw_rect(pymupdf.Rect(0, 0, A4.width, A4.height), color=None, fill=PALE)
    page.draw_rect(pymupdf.Rect(0, 250, 14, 420), color=None, fill=BLUE)
    page.insert_text((60, 300), f"PART {_roman(part.number)}", fontsize=16, fontname="hebo", color=BLUE)
    page.insert_textbox(pymupdf.Rect(58, 315, A4.width - 50, 420), _label(part.title, 60), fontsize=34,
                        fontname="hebo", color=NAVY)
    y = 470
    for c in part.chapters:
        page.insert_text((62, y), _label(f"{c.number}   {c.title}", 75), fontsize=12, fontname="helv", color=NAVY)
        y += 22


def _load_parts() -> list[Part]:
    with session_scope() as s:
        docs = s.exec(select(Document).where(Document.status == "ready").order_by(Document.sort_order)).all()
        docs = [d for d in docs if d.pdf_path and Path(d.pdf_path).exists()]
        rows = [(d.id, d.title, d.subject or "Notes", d.pdf_path) for d in docs]
    parts: list[Part] = []
    by_title: dict[str, Part] = {}
    number = 0
    for doc_id, title, subject, pdf_path in rows:
        part = by_title.get(subject)
        if part is None:
            part = Part(number=len(parts) + 1, title=subject, chapters=[])
            parts.append(part)
            by_title[subject] = part
        number += 1
        part.chapters.append(Chapter(doc_id=doc_id, number=0, title=title, pdf=pymupdf.open(pdf_path)))
    # number chapters in final book order (a later document may join an earlier part)
    n = 0
    for p in parts:
        for c in p.chapters:
            n += 1
            c.number = n
    return parts


def build_book() -> Path:
    parts = _load_parts()
    n_chapters = sum(len(p.chapters) for p in parts)
    toc_pages = max(1, math.ceil((len(parts) + n_chapters) / TOC_LINES_PER_PAGE))
    page_no = 1 + toc_pages + 1  # cover + contents, then 1-based numbering
    for p in parts:
        p.start = page_no
        page_no += 1  # part title page
        for c in p.chapters:
            c.start = page_no
            page_no += c.pdf.page_count
    total = page_no - 1

    book = pymupdf.open()
    _cover(book, len(parts), n_chapters, total)
    links = _toc_pages(book, _toc_entries(parts), toc_pages)
    toc = [[1, "Cover", 1], [1, "Contents", 2]]
    for p in parts:
        _part_page(book, p)
        toc.append([1, _label(f"Part {_roman(p.number)} - {p.title}", 90), p.start])
        for c in p.chapters:
            book.insert_pdf(c.pdf)
            toc.append([2, _label(f"{c.number}. {c.title}", 90), c.start])
            for level, sub, page, *_ in c.pdf.get_toc(simple=True):
                if page >= 1 and sub.strip() and sub.strip() != c.title:
                    toc.append([min(level + 2, toc[-1][0] + 1), _label(sub, 90), page + c.start - 1])
            c.pdf.close()

    for page_index, rect, target in links:
        book[page_index].insert_link({"kind": pymupdf.LINK_GOTO, "from": rect, "page": target - 1})
    for i in range(1, book.page_count):
        r = book[i].rect
        book[i].insert_textbox(pymupdf.Rect(0, r.height - 28, r.width, r.height - 12), f"Megamind  ·  {i + 1}",
                               fontsize=8, fontname="helv", color=GREY, align=1)
    book.set_toc(toc, collapse=2)
    book.set_metadata({"title": "Megamind - The Knowledge Book of Yahia Zaki", "author": "Yahia Zaki",
                       "creator": "Megamind"})

    out = book_path()
    tmp = out.with_suffix(".tmp.pdf")
    book.save(str(tmp), garbage=3, deflate=True)
    book.close()
    tmp.replace(out)

    starts = {c.doc_id: c.start for p in parts for c in p.chapters}
    with session_scope() as s:
        for d in s.exec(select(Document)).all():
            d.book_start_page = starts.get(d.id)
            s.add(d)
        s.commit()
    return out
