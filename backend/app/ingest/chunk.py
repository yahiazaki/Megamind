"""Split a PDF into page-anchored chunks that carry their section path and on-page rectangles."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

TARGET_CHARS = 1100
MIN_CHARS = 220


@dataclass
class ChunkData:
    page: int
    section: str
    text: str
    rects: list = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"\W+", "", s).lower()


def _heading_positions(doc: pymupdf.Document) -> dict[int, list[tuple[float, int, str]]]:
    """page -> [(y, level, title)] found by matching TOC titles against text blocks."""
    out: dict[int, list] = {}
    for level, title, page, *_ in doc.get_toc(simple=False):
        if page < 1:
            continue
        y = 0.0
        key = _norm(title)[:40]
        if key:
            for b in doc[page - 1].get_text("blocks"):
                if b[6] == 0 and _norm(b[4]).startswith(key):
                    y = b[1]
                    break
        out.setdefault(page, []).append((y, level, title.strip()))
    for v in out.values():
        v.sort()
    return out


def chunk_pdf(pdf_path: Path, doc_title: str) -> tuple[list[ChunkData], int]:
    doc = pymupdf.open(str(pdf_path))
    headings = _heading_positions(doc)
    path: list[str] = []          # current heading stack
    chunks: list[ChunkData] = []

    def section() -> str:
        return " > ".join(path) if path else doc_title

    for pno in range(len(doc)):
        page = doc[pno]
        marks = list(headings.get(pno + 1, []))
        blocks = sorted((b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()),
                        key=lambda b: (round(b[1]), b[0]))
        buf, rects = [], []

        def flush():
            if not buf:
                return
            text = re.sub(r"[ \t]+", " ", "\n".join(buf)).strip()
            if len(text) < MIN_CHARS and chunks and chunks[-1].page == pno + 1 and chunks[-1].section == section():
                chunks[-1].text += "\n" + text
                chunks[-1].rects.extend(rects)
            elif text:
                chunks.append(ChunkData(pno + 1, section(), text, list(rects)))
            buf.clear()
            rects.clear()

        for b in blocks:
            # Headings that start at or above this block close the current chunk first
            if marks and marks[0][0] <= b[1] + 1:
                flush()
            while marks and marks[0][0] <= b[1] + 1:
                _, level, title = marks.pop(0)
                del path[level - 1:]
                path.append(title)
            buf.append(b[4].strip())
            rects.append([round(b[0], 1), round(b[1], 1), round(b[2], 1), round(b[3], 1)])
            if sum(len(x) for x in buf) >= TARGET_CHARS:
                flush()
        flush()
        for _, level, title in marks:  # headings below the last text block
            del path[level - 1:]
            path.append(title)
    n = len(doc)
    doc.close()
    return chunks, n
