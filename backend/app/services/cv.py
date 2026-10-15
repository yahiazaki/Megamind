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
from .profile import get_profile, list_tasks

CV_SYSTEM = """You are an expert technical recruiter tailoring a one-page CV to a target job.
You are given the candidate's REAL facts as numbered items. You do not write experience; you SELECT it.

- For each role, pick the 3-5 bullet ids most relevant to the job, most relevant first.
- Pick the 2-3 most relevant projects and, for each, 1-3 of its bullet ids.
- Group the candidate's listed skills into 3-5 categories, job-relevant first. Use only skills from the SKILLS list.
- Write a headline and a 2-3 sentence summary that use only facts present in the items. Do not claim tools,
  certifications, job titles or years of experience the candidate does not have; skills from the job description
  that the candidate lacks must not appear anywhere.
- match_notes is private advice for the candidate: honest fit, real gaps, what to emphasise in an interview.
Return JSON:
{"headline": "...", "summary": "...",
 "experience": [{"id": "E1", "bullets": ["E1.3", "E1.1"]}],
 "projects": [{"id": "P2", "bullets": ["P2.1"]}],
 "skills": [{"category": "...", "items": ["..."]}],
 "match_notes": "..."}"""

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.&/-]*[a-z0-9+#]|[a-z0-9]", re.I)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "cv"


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "")}


def _as_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v]
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


def _task_bullet(t) -> str:
    text = t.title.rstrip(".")
    if t.description:
        text += f": {t.description.rstrip('.')}"
    if t.impact:
        text += f" ({t.impact.rstrip('.')})"
    return text + "."


def _fact_sheet(profile: dict) -> tuple[str, dict[str, str], dict[str, dict], dict[str, dict]]:
    """Number every real fact so the model can only point at them. Returns (text, bullets, roles, projects)."""
    bullets: dict[str, str] = {}
    roles: dict[str, dict] = {}
    projects: dict[str, dict] = {}
    exp = profile.get("experience", [])
    extra: dict[int, list[str]] = {}
    for t in list_tasks():  # work-log entries go under the role at the same company, else the current role
        idx = next((i for i, e in enumerate(exp) if t.company and t.company.lower()[:6] in e.get("company", "").lower()), 0)
        extra.setdefault(idx, []).append(_task_bullet(t))
    lines = ["EXPERIENCE:"]
    for i, e in enumerate(exp, 1):
        rid = f"E{i}"
        roles[rid] = e
        lines.append(f"{rid}: {e.get('role')} at {e.get('company')} ({e.get('start')} - {e.get('end')})")
        for j, b in enumerate(list(e.get("highlights", [])) + extra.get(i - 1, []), 1):
            bullets[f"{rid}.{j}"] = b
            lines.append(f"  {rid}.{j}: {b}")
    lines.append("\nPROJECTS:")
    for i, p in enumerate(profile.get("projects", []), 1):
        pid = f"P{i}"
        projects[pid] = p
        lines.append(f"{pid}: {p.get('name')} [{', '.join(_as_list(p.get('stack')))}]")
        for j, b in enumerate(p.get("highlights", []), 1):
            bullets[f"{pid}.{j}"] = b
            lines.append(f"  {pid}.{j}: {b}")
    skills = [s for items in profile.get("skills", {}).values() for s in items]
    lines += ["\nSKILLS: " + ", ".join(skills),
              "\nCERTIFICATIONS: " + "; ".join(profile.get("certifications", [])),
              "\nEDUCATION: " + "; ".join(f"{e.get('degree')}, {e.get('school')}" for e in profile.get("education", [])),
              "\nPROFILE SUMMARY: " + profile.get("summary", "")]
    return "\n".join(lines), bullets, roles, projects


def _grounded(text: str, allowed: set[str], job_terms: set[str]) -> bool:
    """False when the text uses a term from the job description that appears nowhere in the candidate's facts."""
    return not ((_tokens(text) & job_terms) - allowed)


def _clean_prose(text: str, fallback: str, allowed: set[str], job_terms: set[str]) -> str:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s]
    kept = [s for s in sentences if _grounded(s, allowed, job_terms)]
    # a summary with most of it cut reads badly; the candidate's own summary is better than a fragment
    return " ".join(kept) if len(kept) >= 2 and len(kept) * 2 >= len(sentences) else fallback


def _assemble(profile: dict, data: dict, bullets: dict, roles: dict, projects: dict, job_description: str) -> dict:
    """Build the printed CV from real facts only, using the model's choices for selection and order."""
    facts_text = " ".join([json.dumps(profile, ensure_ascii=False)] + list(bullets.values()))
    allowed = _tokens(facts_text)
    job_terms = _tokens(job_description)

    def pick(ids, prefix: str, limit: int) -> list[str]:
        out = [bullets[i] for i in ids if isinstance(i, str) and i.startswith(prefix + ".") and i in bullets]
        return list(dict.fromkeys(out))[:limit]

    chosen_roles = {x.get("id"): x.get("bullets", []) for x in data.get("experience", []) if isinstance(x, dict)}
    experience = []
    for rid, e in roles.items():  # every real role stays, in profile order
        own = [bullets[k] for k in bullets if k.startswith(rid + ".")]
        chosen = pick(chosen_roles.get(rid, []), rid, 5)
        chosen += [b for b in own if b not in chosen][:max(0, min(3, len(own)) - len(chosen))]
        experience.append({"role": e.get("role", ""), "company": e.get("company", ""), "location": e.get("location", ""),
                           "start": e.get("start", ""), "end": e.get("end", ""), "bullets": chosen})

    proj = []
    for x in data.get("projects", []):
        pid = x.get("id") if isinstance(x, dict) else None
        if pid in projects and pid not in [p["_id"] for p in proj]:
            p = projects[pid]
            chosen = pick(x.get("bullets", []), pid, 3) or p.get("highlights", [])[:2]
            proj.append({"_id": pid, "name": p.get("name", ""), "stack": ", ".join(_as_list(p.get("stack"))),
                         "bullets": chosen})
    if not proj:
        proj = [{"_id": pid, "name": p.get("name", ""), "stack": ", ".join(_as_list(p.get("stack"))),
                 "bullets": p.get("highlights", [])[:2]} for pid, p in list(projects.items())[:3]]
    for p in proj:
        p.pop("_id")

    real_skills = {s.lower(): s for items in profile.get("skills", {}).values() for s in items}
    skills, used = [], set()
    for grp in data.get("skills", []):
        if not isinstance(grp, dict):
            continue
        items = [real_skills[i.lower()] for i in _as_list(grp.get("items")) if i.lower() in real_skills
                 and i.lower() not in used]
        used.update(i.lower() for i in items)
        if items:
            skills.append({"category": str(grp.get("category", "Skills")), "items": items})
    if not skills:
        skills = [{"category": k, "items": v} for k, v in profile.get("skills", {}).items()]

    headline = data.get("headline", "")
    return {
        "headline": headline if headline and _grounded(headline, allowed, job_terms) else profile.get("headline", ""),
        "summary": _clean_prose(data.get("summary", ""), profile.get("summary", ""), allowed, job_terms),
        "experience": experience,
        "projects": proj,
        "skills": skills,
        "certifications": list(profile.get("certifications", [])),
        "education": list(profile.get("education", [])),
        "match_notes": data.get("match_notes", ""),
    }


def generate(job_description: str, extra: str = "", target_title: str = "") -> dict:
    profile = get_profile()
    facts, bullets, roles, projects = _fact_sheet(profile)
    user = (f"TARGET JOB TITLE: {target_title or '(infer from the description)'}\n\nJOB DESCRIPTION:\n"
            f"{job_description[:6000]}\n\nEXTRA INSTRUCTIONS FROM THE CANDIDATE:\n{extra or 'none'}\n\n"
            f"CANDIDATE FACTS:\n{facts}")
    raw = llm.chat_json(CV_SYSTEM, user, temperature=0.2)
    data = _assemble(profile, raw, bullets, roles, projects, job_description + " " + target_title)
    out_dir = get_settings().data_dir / "cv" / f"{datetime.now():%Y%m%d-%H%M%S}-{_slug(target_title or data.get('headline', 'cv'))}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cv.json").write_text(json.dumps({"input": {"job_description": job_description, "extra": extra,
                                                           "target_title": target_title}, "cv": data},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    pdf_ok, pdf_error = _render_one_page(profile, data, out_dir)
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


def _render_one_page(profile: dict, cv: dict, out_dir: Path) -> tuple[bool, str]:
    """Render docx + PDF; tighten type, then trim the lowest-ranked bullets, until the PDF fits on one page."""
    import pymupdf

    attempts = [(10.5, 0), (10, 0), (9.5, 0), (9.5, 1), (9.5, 2)]
    for size, trim in attempts:
        cv_try = json.loads(json.dumps(cv))
        for e in cv_try.get("experience", []) + cv_try.get("projects", []):
            keep = max(2, len(e.get("bullets", [])) - trim)
            e["bullets"] = e.get("bullets", [])[:keep]
        docx_path = render_docx(profile, cv_try, out_dir / "cv.docx", size=size)
        try:
            word_to_pdf(docx_path, out_dir / "cv.pdf")
        except Exception as e:
            return False, str(e)
        with pymupdf.open(out_dir / "cv.pdf") as doc:
            if doc.page_count <= 1:
                break
    return True, ""


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


def _section(d, title: str, gap: float = 8):
    p = d.add_paragraph()
    p.paragraph_format.space_before = Pt(gap)
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


def render_docx(profile: dict, cv: dict, out: Path, size: float = 10.5) -> Path:
    d = docx.Document()
    for sec in d.sections:
        sec.top_margin = sec.bottom_margin = Inches(0.5 if size > 10 else 0.4)
        sec.left_margin = sec.right_margin = Inches(0.6 if size > 10 else 0.5)
    normal = d.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(size)
    normal.paragraph_format.space_after = Pt(2 if size > 10 else 0)
    gap = 8 if size > 10 else 5

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
        _section(d, "Summary", gap)
        d.add_paragraph(cv["summary"])
    if cv.get("experience"):
        _section(d, "Experience", gap)
        for e in cv["experience"]:
            _two_col(d, e.get("role", ""), f"{e.get('start', '')} – {e.get('end', '')}".strip(" –"))
            _two_col(d, e.get("company", ""), e.get("location", ""), bold=False, italic=True)
            for b in e.get("bullets", []):
                _bullet(d, b)
    if cv.get("projects"):
        _section(d, "Projects", gap)
        for p in cv["projects"]:
            par = d.add_paragraph()
            par.paragraph_format.space_after = Pt(0)
            par.add_run(p.get("name", "")).bold = True
            if p.get("stack"):
                par.add_run(f"  |  {p['stack']}").italic = True
            for b in p.get("bullets", []):
                _bullet(d, b)
    if cv.get("skills"):
        _section(d, "Technical Skills", gap)
        for s in cv["skills"]:
            par = d.add_paragraph()
            par.paragraph_format.space_after = Pt(0)
            par.add_run(f"{s.get('category', '')}: ").bold = True
            par.add_run(", ".join(s.get("items", [])))
    if cv.get("certifications"):
        _section(d, "Certifications & Courses", gap)
        for c in cv["certifications"]:
            _bullet(d, c)
    if cv.get("education"):
        _section(d, "Education", gap)
        for e in cv["education"]:
            _two_col(d, e.get("degree", ""), f"{e.get('start', '')} – {e.get('end', '')}".strip(" –"))
            _two_col(d, e.get("school", ""), e.get("location", ""), bold=False, italic=True)
    d.save(str(out))
    return out
