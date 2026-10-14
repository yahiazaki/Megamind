"""Paragraph-level translation of .docx files.

Only the text of a paragraph is replaced; images, tables, styles and headings are kept, so the
translated document renders like the original. Paragraphs are addressed by their position in
document order, which makes extract -> translate -> apply round-trips stable.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Callable, Iterable

import docx
from docx.oxml.ns import qn

from .detect import needs_translation

log = logging.getLogger(__name__)
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _own_texts(p_el) -> list:
    """w:t elements that belong to this paragraph (not to a nested text-box paragraph)."""
    out = []
    for t in p_el.iter(qn("w:t")):
        anc = t.getparent()
        while anc is not None and anc.tag != qn("w:p"):
            anc = anc.getparent()
        if anc is p_el:
            out.append(t)
    return out


def paragraph_text(p_el) -> str:
    return "".join(t.text or "" for t in _own_texts(p_el))


def set_paragraph_text(p_el, new_text: str) -> None:
    ts = _own_texts(p_el)
    if not ts:
        return
    ts[0].text = new_text
    ts[0].set(XML_SPACE, "preserve")
    for t in ts[1:]:
        t.getparent().remove(t)


def iter_paragraph_elements(document) -> Iterable:
    return document.element.body.iter(qn("w:p"))


def extract(docx_path: Path) -> list[dict]:
    """Return [{id, text}] for every paragraph that needs translation."""
    d = docx.Document(str(docx_path))
    items = []
    for i, p_el in enumerate(iter_paragraph_elements(d)):
        text = paragraph_text(p_el)
        if needs_translation(text):
            items.append({"id": i, "text": text})
    return items


def apply(docx_path: Path, out_path: Path, translations: dict[int, str]) -> int:
    d = docx.Document(str(docx_path))
    changed = 0
    for i, p_el in enumerate(iter_paragraph_elements(d)):
        if i in translations and translations[i].strip():
            set_paragraph_text(p_el, translations[i].strip())
            changed += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(out_path))
    return changed


# ---------------------------------------------------------------------------
# Automatic translation with the local LLM (used for documents uploaded later)
# ---------------------------------------------------------------------------

TRANSLATE_SYSTEM = """You translate study notes into clear English.
The notes mix English with Egyptian Arabic written in Arabic script and with "Franco" (Arabizi):
Egyptian Arabic in Latin letters where digits are letters (3=ع, 2=ء/ق, 7=ح, 5=خ, 8=غ, 6=ط).
Common Franco words: l/el=the, w=and, fl=in the, bta3=of, 3shan=because/so that, ya3ny=meaning,
momken=can, lazm=must, msh=not, keda=like this, ba2a=then, zy=like, 3yz=want, haga=thing, de/da=this.

Rules:
- Translate the meaning faithfully into natural English. Do not summarise or drop details.
- Keep technical terms, code, commands, numbers, names and English parts unchanged.
- Return ONLY JSON: {"translations": {"<id>": "<english>", ...}} with every id you were given."""


def _batches(items: list[dict], max_chars: int = 2500) -> Iterable[list[dict]]:
    batch, size = [], 0
    for it in items:
        if batch and size + len(it["text"]) > max_chars:
            yield batch
            batch, size = [], 0
        batch.append(it)
        size += len(it["text"])
    if batch:
        yield batch


def translate_items(items: list[dict], chat_json: Callable[[str, str], dict],
                    progress: Callable[[int, int], None] | None = None) -> dict[int, str]:
    """Translate paragraphs with an LLM. chat_json(system, user) must return parsed JSON."""
    result: dict[int, str] = {}
    done = 0
    for batch in _batches(items):
        payload = {str(it["id"]): it["text"] for it in batch}
        user = "Translate these paragraphs:\n" + json.dumps(payload, ensure_ascii=False, indent=1)
        try:
            data = chat_json(TRANSLATE_SYSTEM, user)
            tr = data.get("translations", data) if isinstance(data, dict) else {}
            for k, v in tr.items():
                if re.fullmatch(r"\d+", str(k)) and isinstance(v, str):
                    result[int(k)] = v
        except Exception as e:  # keep going; untranslated paragraphs stay as they were
            log.warning("translation batch failed: %s", e)
        done += len(batch)
        if progress:
            progress(done, len(items))
    return result
