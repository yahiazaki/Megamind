"""Extract .docx chapters to markdown with image markers, as raw material for the book rewrite.

Usage: python scripts/book_extract.py <docx> [<docx> ...]
Writes data/book_src/raw/<stem>.md and images to data/book_src/images/<stem>-<n>.<ext>.
Images become [[IMG:<file>]] markers at the position they appeared; headings keep their level.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import docx
from docx.oxml.ns import qn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402

R_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"


def _text(p) -> str:
    out = []
    for node in p.iter():
        if node.tag == qn("w:t") and node.text:
            out.append(node.text)
        elif node.tag == qn("w:tab"):
            out.append("\t")
        elif node.tag in (qn("w:br"), qn("w:cr")):
            out.append("\n")
    return "".join(out).strip()


def _heading_level(p, styles) -> int:
    pstyle = p.find(qn("w:pPr") + "/" + qn("w:pStyle"))
    name = styles.get(pstyle.get(qn("w:val")), "") if pstyle is not None else ""
    m = re.match(r"(?i)heading\s*(\d)", name)
    if m:
        return int(m.group(1))
    return 1 if name.lower() == "title" else 0


def _is_list(p) -> int:
    num = p.find(qn("w:pPr") + "/" + qn("w:numPr"))
    if num is None:
        return 0
    ilvl = num.find(qn("w:ilvl"))
    return 1 + (int(ilvl.get(qn("w:val"))) if ilvl is not None else 0)


def extract(path: Path, out_dir: Path, img_dir: Path) -> Path:
    d = docx.Document(str(path))
    styles = {s.style_id: s.name for s in d.styles}
    stem = path.stem
    lines: list[str] = []
    n_img = 0

    def save_images(el):
        nonlocal n_img
        for blip in el.iter(qn("a:blip")):
            rid = blip.get(R_EMBED)
            part = d.part.related_parts.get(rid) if rid else None
            if part is None:
                continue
            ext = Path(part.partname).suffix.lower() or ".png"
            if ext in (".emf", ".wmf"):
                continue  # vector office formats do not render outside Word
            n_img += 1
            name = f"{stem}-{n_img:03d}{ext}"
            (img_dir / name).write_bytes(part.blob)
            lines.append(f"[[IMG:{name}]]")

    for el in d.element.body.iterchildren():
        if el.tag == qn("w:p"):
            text = _text(el)
            level = _heading_level(el, styles)
            lst = _is_list(el)
            if text:
                if level:
                    lines.append("")
                    lines.append("#" * min(level + 1, 4) + " " + text.replace("\n", " "))
                elif lst:
                    lines.append("  " * (lst - 1) + "- " + text.replace("\n", " "))
                else:
                    lines.append(text)
            save_images(el)
        elif el.tag == qn("w:tbl"):
            rows = []
            for tr in el.iter(qn("w:tr")):
                cells = [" ".join(_text(p) for p in tc.iter(qn("w:p"))).replace("|", "\\|").strip()
                         for tc in tr.iter(qn("w:tc"))]
                rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines.append("")
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("|" + " --- |" * width)
                lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                lines.append("")
            save_images(el)

    md = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
    out = out_dir / f"{stem}.md"
    out.write_text(md, encoding="utf-8")
    return out


if __name__ == "__main__":
    base = get_settings().data_dir / "book_src"
    out_dir, img_dir = base / "raw", base / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    for arg in sys.argv[1:]:
        out = extract(Path(arg), out_dir, img_dir)
        text = out.read_text(encoding="utf-8")
        print(f"{out.name}: {len(text):,} chars, {text.count('[[IMG:')} images, {len(re.findall(r'^#+ ', text, re.M))} headings")
