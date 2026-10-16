"""Rewrite rough notes into book-style chapters with the local model, section by section.

Used for documents added after the book was written (notes from the workspace, uploads with "polish" on), so new
material reads like the rest of the book. Facts are kept: a section whose rewrite drops too many of its technical
terms falls back to the original text.
"""
from __future__ import annotations

import logging
import re
from typing import Callable

log = logging.getLogger(__name__)

SECTION_CHARS = 3500
MIN_TERM_COVERAGE = 0.75

POLISH_SYSTEM = """You are the editor of "Megamind", a personal technical study book. Rewrite the given rough notes
section into clear, well-organised book text.

Rules:
- Keep EVERY fact, command, number, example and code snippet. Do not add new facts, opinions or filler.
- Organise with markdown: "### " sub-headings where the topic changes, short paragraphs, "- " bullets for lists,
  tables for comparisons, fenced code blocks for code and commands.
- Fix grammar and remove repetition. Write in English. Do not mention "the notes" or "the author".
- Keep image markers like [[IMG:...]] exactly as they are, next to the text they illustrate.
Return JSON: {"heading": "a clear, specific section title", "markdown": "the rewritten section body"}"""

TERM_RE = re.compile(r"`[^`]+`|\b[A-Z][A-Za-z0-9+#./-]{1,}\b|\b\w+\(\)|\b\d+(?:\.\d+)?\b")


def _terms(text: str) -> set[str]:
    return {t.lower() for t in TERM_RE.findall(text)}


MAX_NOVELTY = 0.3
WORD_RE = re.compile(r"[a-z][a-z0-9+#-]{3,}")


def coverage(original: str, rewritten: str) -> float:
    orig = _terms(original)
    if not orig:
        return 1.0
    new = _terms(rewritten)
    return len(orig & new) / len(orig)


def novelty(original: str, rewritten: str) -> float:
    """Share of content words in the rewrite that never appear in the original: a proxy for invented facts."""
    orig = set(WORD_RE.findall(original.lower()))
    new = set(WORD_RE.findall(rewritten.lower()))
    return len(new - orig) / len(new) if new else 0.0


def _keep_known_images(original: str, rewritten: str) -> str:
    known = set(re.findall(r"\[\[IMG:[^\]]+\]\]", original))
    return re.sub(r"\[\[IMG:[^\]]+\]\]", lambda m: m.group(0) if m.group(0) in known else "", rewritten)


def split_sections(markdown: str) -> list[tuple[str, str]]:
    """[(heading, body)] split on ## / # headings, with long bodies cut at paragraph boundaries."""
    sections: list[tuple[str, str]] = []
    heading, buf = "", []
    for line in markdown.splitlines():
        m = re.match(r"^#{1,2}\s+(.*)", line)
        if m:
            if heading or "".join(buf).strip():
                sections.append((heading, "\n".join(buf).strip()))
            heading, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if heading or "".join(buf).strip():
        sections.append((heading, "\n".join(buf).strip()))

    out = []
    for h, body in sections:
        if len(body) <= SECTION_CHARS:
            out.append((h, body))
            continue
        piece, n = [], 0
        for para in re.split(r"\n\s*\n", body):
            if n + len(para) > SECTION_CHARS and piece:
                out.append((h, "\n\n".join(piece)))
                h, piece, n = "", [], 0  # continuation keeps the previous heading context
            piece.append(para)
            n += len(para)
        if piece:
            out.append((h, "\n\n".join(piece)))
    return out


def polish_markdown(markdown: str, title: str, chat_json: Callable, progress: Callable | None = None) -> str:
    """Return a book-style chapter (markdown starting with '# title')."""
    title_line = re.match(r"^#\s+(.*)", markdown.strip())
    if title_line:
        markdown = markdown.strip()[title_line.end():]
    sections = split_sections(markdown)
    out = [f"# {title}", ""]
    for i, (heading, body) in enumerate(sections, 1):
        if progress:
            progress(i - 1, len(sections))
        if not body.strip():
            if heading:
                out += [f"## {heading}", ""]
            continue
        user = f"CHAPTER: {title}\nSECTION HEADING: {heading or '(none)'}\n\nNOTES:\n{body}"
        try:
            data = chat_json(POLISH_SYSTEM, user, temperature=0.2)
            new_heading = str(data.get("heading") or heading).strip()
            new_body = _keep_known_images(body, str(data.get("markdown") or "").strip())
            cov, nov = coverage(body, new_body), novelty(body, new_body)
            if cov < MIN_TERM_COVERAGE or nov > MAX_NOVELTY:
                log.info("rewrite of %r rejected (coverage %.2f, novelty %.2f), keeping original", heading, cov, nov)
                new_heading, new_body = heading, body
        except Exception as e:
            log.warning("polish failed for section %r: %s", heading, e)
            new_heading, new_body = heading, body
        # continuation pieces of a long section stay under the same heading
        if new_heading and (heading or i == 1):
            out += [f"## {new_heading}", ""]
        out += [new_body, ""]
    if progress:
        progress(len(sections), len(sections))
    return "\n".join(out).strip() + "\n"
