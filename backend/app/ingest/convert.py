"""File conversions: anything -> .docx -> .pdf.

Word (via COM automation) gives the best fidelity for documents with images and Arabic text.
LibreOffice is used as a fallback when Word is not available.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

log = logging.getLogger(__name__)
_word_lock = threading.Lock()

WORD_EXTS = {".docx", ".doc", ".rtf", ".odt"}
TEXT_EXTS = {".md", ".markdown", ".txt"}
SUPPORTED = WORD_EXTS | TEXT_EXTS | {".pdf"}

WD_EXPORT_PDF = 17
WD_EXPORT_HEADING_BOOKMARKS = 1
WD_FORMAT_DOCX = 16


def _soffice() -> str | None:
    for p in (shutil.which("soffice"), r"C:\Program Files\LibreOffice\program\soffice.exe"):
        if p and Path(p).exists():
            return p
    return None


def _with_word(fn):
    """Run fn(word_app) inside a private, invisible Word instance."""
    import pythoncom
    import win32com.client

    with _word_lock:
        pythoncom.CoInitialize()
        word = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            return fn(word)
        finally:
            if word is not None:
                try:
                    word.Quit(SaveChanges=0)
                except Exception:
                    pass
            pythoncom.CoUninitialize()


def word_to_pdf(src: Path, out_pdf: Path) -> Path:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    try:
        def run(word):
            d = word.Documents.Open(str(src.resolve()), ReadOnly=True, AddToRecentFiles=False,
                                    ConfirmConversions=False, Visible=False)
            try:
                d.ExportAsFixedFormat(OutputFileName=str(out_pdf.resolve()), ExportFormat=WD_EXPORT_PDF,
                                      OpenAfterExport=False, OptimizeFor=0,
                                      CreateBookmarks=WD_EXPORT_HEADING_BOOKMARKS, DocStructureTags=True)
            finally:
                d.Close(SaveChanges=0)
        _with_word(run)
        return out_pdf
    except ImportError:
        pass
    except Exception as e:
        log.warning("Word conversion failed for %s: %s", src, e)
        if not _soffice():
            raise
    soffice = _soffice()
    if not soffice:
        raise RuntimeError("Neither Microsoft Word nor LibreOffice is available for PDF conversion")
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_pdf.parent), str(src)],
                   check=True, timeout=300, capture_output=True)
    produced = out_pdf.parent / (src.stem + ".pdf")
    if produced != out_pdf:
        produced.replace(out_pdf)
    return out_pdf


def to_docx(src: Path, out_docx: Path) -> Path:
    """Convert anything Word can open (.doc, .rtf, .odt, text PDFs via PDF reflow) into .docx."""
    def run(word):
        d = word.Documents.Open(str(src.resolve()), ConfirmConversions=False, ReadOnly=True,
                                AddToRecentFiles=False, Visible=False)
        try:
            d.SaveAs2(str(out_docx.resolve()), FileFormat=WD_FORMAT_DOCX)
        finally:
            d.Close(SaveChanges=0)
    _with_word(run)
    return out_docx


# ---------------------------------------------------------------------------
# Markdown / plain text -> .docx
# ---------------------------------------------------------------------------

INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


def _add_inline(par, text: str):
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            par.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`"):
            run = par.add_run(part[1:-1])
            run.font.name = "Consolas"
            run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        else:
            par.add_run(part)


def _split_row(line: str) -> list[str]:
    line = line.strip().strip("|")
    cells = re.split(r"(?<!\\)\|", line)
    return [c.strip().replace("\\|", "|") for c in cells]


def markdown_to_docx(text: str, out_docx: Path, title: str | None = None) -> Path:
    d = docx.Document()
    style = d.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    if title and not text.lstrip().startswith("# "):
        d.add_heading(title, level=0)

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            p = d.add_paragraph()
            run = p.add_run("\n".join(code))
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
            p.paragraph_format.left_indent = Pt(12)
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            header = _split_row(stripped)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            table = d.add_table(rows=1 + len(rows), cols=len(header))
            table.style = "Table Grid"
            for c, h in enumerate(header):
                cell = table.rows[0].cells[c]
                cell.text = ""
                cell.paragraphs[0].add_run(h.replace("**", "")).bold = True
            for r, row in enumerate(rows, start=1):
                for c in range(len(header)):
                    cell = table.rows[r].cells[c]
                    cell.text = ""
                    _add_inline(cell.paragraphs[0], row[c] if c < len(row) else "")
            d.add_paragraph()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            d.add_heading(m.group(2).strip(), level=0 if level == 1 else level - 1)
        elif re.match(r"^[-*]\s+", stripped):
            _add_inline(d.add_paragraph(style="List Bullet"), re.sub(r"^[-*]\s+", "", stripped))
        elif re.match(r"^\d+\.\s+", stripped):
            _add_inline(d.add_paragraph(style="List Number"), re.sub(r"^\d+\.\s+", "", stripped))
        elif stripped.startswith(">"):
            p = d.add_paragraph(style="Intense Quote")
            _add_inline(p, stripped.lstrip("> "))
        elif stripped:
            _add_inline(d.add_paragraph(), stripped)
        i += 1

    for p in d.paragraphs:
        if p.style.name == "Title":
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    out_docx.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(out_docx))
    return out_docx
