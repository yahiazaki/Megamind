"""Tailored CV generation: LLM picks and rephrases real experience for a job description -> .docx + .pdf."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from .. import llm
from ..config import get_settings
from ..ingest.convert import word_to_pdf
from .profile import get_profile, profile_context

CV_SYSTEM = """You are an expert technical recruiter and resume writer. Build a one-page, ATS-friendly CV for the
candidate, tailored to the target job, using ONLY facts from the candidate's profile and work log.

Hard rules:
- Never invent employers, titles, dates, metrics, certifications or technologies. You may rephrase, reorder, merge
  and select bullets, and mirror the job's keywords only where the candidate genuinely has that experience.
- Bullets start with a strong verb, show impact, and are at most ~25 words. 3-6 bullets per role, 2-3 projects.
- Order skills so the job's most relevant ones come first. Keep the candidate's real education.
Return JSON:
{"headline": "...", "summary": "2-3 sentences",
 "experience": [{"role": "...", "company": "...", "location": "...", "start": "...", "end": "...",
                 "bullets": ["..."]}],
 "projects": [{"name": "...", "stack": "comma separated", "bullets": ["..."]}],
 "skills": [{"category": "...", "items": ["..."]}],
 "certifications": ["..."],
 "education": [{"degree": "...", "school": "...", "location": "...", "start": "...", "end": "..."}],
 "match_notes": "2-3 sentences for the candidate (not printed): fit, gaps, what to emphasise in the interview"}"""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "cv"


def generate(job_description: str, extra: str = "", target_title: str = "") -> dict:
    user = (f"TARGET JOB TITLE: {target_title or '(infer from the description)'}\n\nJOB DESCRIPTION:\n"
            f"{job_description[:6000]}\n\nEXTRA INSTRUCTIONS FROM THE CANDIDATE:\n{extra or 'none'}\n\n"
            f"{profile_context(public=False)}")
    data = llm.chat_json(CV_SYSTEM, user, temperature=0.3)
    profile = get_profile()
    out_dir = get_settings().data_dir / "cv" / f"{datetime.now():%Y%m%d-%H%M%S}-{_slug(target_title or data.get('headline', 'cv'))}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cv.json").write_text(json.dumps({"input": {"job_description": job_description, "extra": extra,
                                                           "target_title": target_title}, "cv": data},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    docx_path = render_docx(profile, data, out_dir / "cv.docx")
    pdf_ok, pdf_error = True, ""
    try:
        word_to_pdf(docx_path, out_dir / "cv.pdf")
    except Exception as e:
        pdf_ok, pdf_error = False, str(e)
    return {"id": out_dir.name, "cv": data, "pdf": pdf_ok, "pdf_error": pdf_error}


def list_generated() -> list[dict]:
    root = get_settings().data_dir / "cv"
    out = []
    for d in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True):
        meta = json.loads((d / "cv.json").read_text(encoding="utf-8")) if (d / "cv.json").exists() else {}
        out.append({"id": d.name, "title": meta.get("input", {}).get("target_title") or meta.get("cv", {}).get("headline", ""),
                    "pdf": (d / "cv.pdf").exists(), "created": d.name[:15]})
    return out


def file_for(cv_id: str, ext: str) -> Path | None:
    if not re.fullmatch(r"[\w\-]+", cv_id) or ext not in ("pdf", "docx"):
        return None
    p = get_settings().data_dir / "cv" / cv_id / f"cv.{ext}"
    return p if p.exists() else None


# ---------------------------------------------------------------------------
# .docx rendering
# ---------------------------------------------------------------------------

ACCENT = RGBColor(0x0B, 0x3F, 0x9E)


def _bottom_border(par):
    p_pr = par._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "0B3F9E")):
        bottom.set(qn(k), v)
    bdr.append(bottom)
    p_pr.append(bdr)


def _hyperlink(par, url: str, text: str):
    r_id = par.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                              is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0B3F9E")
    rpr.append(color)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    par._p.append(link)


def _section(d, title: str):
    p = d.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(title.upper())
    r.bold, r.font.size, r.font.color.rgb = True, Pt(11), ACCENT
    _bottom_border(p)


def _two_col(d, left: str, right: str, bold=True, italic=False, width=Inches(7.3)):
    p = d.add_paragraph()
    p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
    p.paragraph_format.space_after = Pt(0)
    a = p.add_run(left)
    a.bold, a.italic = bold, italic
    b = p.add_run("\t" + right)
    b.italic = italic
    return p


def _bullet(d, text: str):
    p = d.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(0)
    p.add_run(text)


def render_docx(profile: dict, cv: dict, out: Path) -> Path:
    d = docx.Document()
    for sec in d.sections:
        sec.top_margin = sec.bottom_margin = Inches(0.5)
        sec.left_margin = sec.right_margin = Inches(0.6)
    normal = d.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(10.5)

    name = d.add_paragraph()
    name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = name.add_run(profile.get("name", "").upper())
    r.bold, r.font.size, r.font.color.rgb = True, Pt(20), ACCENT
    name.paragraph_format.space_after = Pt(0)
    head = d.add_paragraph()
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    head.add_run(cv.get("headline") or profile.get("headline", "")).italic = True
    head.paragraph_format.space_after = Pt(0)

    contact = d.add_paragraph()
    contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    bits = [x for x in (profile.get("phone"), profile.get("email"), profile.get("location")) if x]
    contact.add_run("  |  ".join(bits))
    links = profile.get("links", {})
    for label in ("linkedin", "github", "website"):
        if links.get(label):
            contact.add_run("  |  ")
            url = links[label] if links[label].startswith("http") else "https://" + links[label]
            _hyperlink(contact, url, {"linkedin": "LinkedIn", "github": "GitHub"}.get(label, label.capitalize()))

    if cv.get("summary"):
        _section(d, "Summary")
        d.add_paragraph(cv["summary"])
    if cv.get("experience"):
        _section(d, "Experience")
        for e in cv["experience"]:
            _two_col(d, e.get("role", ""), f"{e.get('start', '')} – {e.get('end', '')}".strip(" –"))
            _two_col(d, e.get("company", ""), e.get("location", ""), bold=False, italic=True)
            for b in e.get("bullets", []):
                _bullet(d, b)
    if cv.get("projects"):
        _section(d, "Projects")
        for p in cv["projects"]:
            par = d.add_paragraph()
            par.paragraph_format.space_after = Pt(0)
            par.add_run(p.get("name", "")).bold = True
            if p.get("stack"):
                par.add_run(f"  |  {p['stack']}").italic = True
            for b in p.get("bullets", []):
                _bullet(d, b)
    if cv.get("skills"):
        _section(d, "Technical Skills")
        for s in cv["skills"]:
            par = d.add_paragraph()
            par.paragraph_format.space_after = Pt(0)
            par.add_run(f"{s.get('category', '')}: ").bold = True
            par.add_run(", ".join(s.get("items", [])))
    if cv.get("certifications"):
        _section(d, "Certifications & Courses")
        for c in cv["certifications"]:
            _bullet(d, c)
    if cv.get("education"):
        _section(d, "Education")
        for e in cv["education"]:
            _two_col(d, e.get("degree", ""), f"{e.get('start', '')} – {e.get('end', '')}".strip(" –"))
            _two_col(d, e.get("school", ""), e.get("location", ""), bold=False, italic=True)
    d.save(str(out))
    return out
