"""Study sessions: grounded chat, quizzes, grading, reminders and the /end summary."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Iterator

from sqlmodel import select

from .. import llm
from ..db import session_scope
from ..models import AnswerCache, ChatSession, Message, QuizItem
from ..rag.index import Hit, build_queries, citations_json, format_context, index
from . import reminders, whatsapp

log = logging.getLogger(__name__)

STUDY_SYSTEM = """You are Megamind, Yahia's personal study assistant. Yahia wrote these notes over five years of
university and self-study (security, networking, Bash, APIs, databases, Python, design patterns, embedded/RTOS).

How to answer:
- Yahia may write in English, Egyptian Arabic or Franco-Arabic (Arabic in Latin letters: 3=ع, 7=ح, 2=ء).
  ALWAYS reply in clear English, whatever language the question is in.
- Answer ONLY from the NOTES excerpts below (and any @mentioned workspace notes). Do not use outside knowledge, and
  do not fill gaps with your own facts.
- If the excerpts do not contain the answer, reply with exactly this sentence and nothing else:
  "I don't know — this isn't covered in your book."
  If they cover only part of the question, answer that part and say which part is not covered.
- Cite the excerpts inline at the end of the sentence that uses them, like "TCP retransmits lost segments [2]."
  Never put citations on their own line.
- Teach like a sharp tutor: concise structured markdown (usually under 250 words unless asked for depth), examples
  taken from the notes, and a one-line takeaway when useful.
- Never invent citations or page numbers."""

TURN_REMINDER = ("\n\n(Reply in English, using only the excerpts. Cite them inline by number, e.g. [1] or [3]. "
                 "If they don't contain the answer, say you don't know.)")

NOT_IN_BOOK = "I don't know — this isn't covered in your book."
MIN_SIMILARITY = 0.47        # below this, no passage in the book is about the question (bge-m3 cosine)
CONFIDENT_SIMILARITY = 0.66  # above this the passages are clearly on topic; in between, check coverage first

COVERAGE_SYSTEM = """You check a student's study book. Decide whether the NOTES below contain the information needed
to answer the QUESTION, fully or in part. Judge ONLY by what the notes say — not by what you know yourself.
Return JSON: {"covered": true | false}"""

HELP_TEXT = """**Commands**
- `/quiz [number] [topic]` — test me (e.g. `/quiz 5 TCP handshake`). With no topic I quiz you on what we discussed.
- `/remind <what and when>` — add a reminder to Google Calendar (e.g. `/remind revise subnetting tomorrow 6pm`).
- `/end` — finish the session: I summarise strengths, weaknesses and what to study next, and send it to WhatsApp.
- `/help` — this list.

Just ask normally for anything else: I answer from your notes and show where each part came from."""

REMINDER_INTENT = re.compile(r"^\s*(remind me|set a reminder|ذكرني|فكرني|fakarny|fakarni|fakkarni|fakkarny)\b", re.I)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _save_message(session_id: int, role: str, content: str, kind: str = "text", payload: str = "") -> Message:
    with session_scope() as s:
        m = Message(session_id=session_id, role=role, content=content, kind=kind, payload=payload)
        s.add(m)
        sess = s.get(ChatSession, session_id)
        if role == "user" and sess.title == "New session" and not content.startswith("/"):
            sess.title = content[:60]
            s.add(sess)
        s.commit()
        s.refresh(m)
        return m


def _history(session_id: int, limit: int = 10) -> list[dict]:
    with session_scope() as s:
        rows = s.exec(select(Message).where(Message.session_id == session_id, Message.kind == "text")
                      .order_by(Message.id.desc()).limit(limit)).all()
        return [{"role": m.role, "content": m.content} for m in reversed(rows)]


# ---------------------------------------------------------------------------
# Chat turn
# ---------------------------------------------------------------------------

def handle_message(session_id: int, text: str, mentions: list[int] | None = None) -> Iterator[str]:
    text = text.strip()
    history = _history(session_id)
    _save_message(session_id, "user", text)
    cmd = text.split()[0].lower() if text else ""
    try:
        if cmd == "/help":
            _save_message(session_id, "assistant", HELP_TEXT)
            yield sse({"type": "token", "text": HELP_TEXT})
        elif cmd == "/end":
            yield sse({"type": "status", "text": "Summarising the session…"})
            summary = end_session(session_id)
            yield sse({"type": "summary", "data": summary})
        elif cmd == "/quiz":
            yield sse({"type": "status", "text": "Writing questions from your notes…"})
            n, topic = _parse_quiz_args(text)
            items = generate_quiz(session_id, topic, n, history)
            yield sse({"type": "quiz", "items": items})
        elif cmd == "/remind" or REMINDER_INTENT.match(text):
            yield sse({"type": "status", "text": "Adding the reminder…"})
            body = text[len("/remind"):].strip() if cmd == "/remind" else text
            r = reminders.parse_and_create(body)
            data = {"id": r.id, "title": r.title, "start": r.start.isoformat(), "all_day": r.all_day,
                    "google": bool(r.google_event_id)}
            where = "Google Calendar" if r.google_event_id else "Megamind (Google Calendar is not connected)"
            when = r.start.strftime("%A %d %B") + ("" if r.all_day else r.start.strftime(" at %H:%M"))
            msg = f"⏰ Reminder saved to {where}: **{r.title}** — {when}."
            _save_message(session_id, "assistant", msg, kind="reminder", payload=json.dumps(data))
            yield sse({"type": "reminder", "data": data, "text": msg})
        else:
            yield from _rag_answer(session_id, text, history, mentions or [])
    except Exception as e:
        log.exception("chat turn failed")
        yield sse({"type": "error", "text": f"Something went wrong: {e}"})
    yield sse({"type": "done"})


def _cache_key(text: str, history: list[dict]) -> str:
    """Same question → same key. Short follow-ups ("explain more") depend on the conversation, so the previous answer
    is part of their key; the book fingerprint expires every answer when the book changes."""
    normal = re.sub(r"\s+", " ", text.lower()).strip(" ?!.")
    context = ""
    recent = [m for m in history if m["role"] == "assistant"]
    if recent and len(text.split()) <= 6:
        context = recent[-1]["content"][:2000]
    raw = f"{normal}\n{context}\n{index.fingerprint()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cached(key: str) -> AnswerCache | None:
    with session_scope() as s:
        row = s.get(AnswerCache, key)
        if row:
            row.hits += 1
            s.add(row)
            s.commit()
            s.refresh(row)
        return row


def _store(key: str, question: str, answer: str, citations: list) -> None:
    with session_scope() as s:
        s.merge(AnswerCache(key=key, question=question, answer=answer, sources=json.dumps(citations)))
        s.commit()


def _covered(text: str, queries: list[str], hits: list[Hit]) -> bool:
    question = text if len(queries) < 2 else f"{text}  (meaning: {' / '.join(queries[1:])})"
    try:
        verdict = llm.chat_json(COVERAGE_SYSTEM, f"QUESTION: {question}\n\nNOTES:\n{format_context(hits)}",
                                temperature=0)
        return bool(verdict.get("covered"))
    except Exception as e:
        log.warning("coverage check failed: %s", e)
        return True     # fall back to the strict answer prompt


def _rag_answer(session_id: int, text: str, history: list[dict], mentions: list[int]) -> Iterator[str]:
    if not index.stats()["chunks"]:
        msg = "Your book is still loading — ask again in a few seconds."
        yield sse({"type": "token", "text": msg})
        _save_message(session_id, "assistant", msg)
        return
    # answers that use @mentioned notes are not cached: the notes can change at any time
    key = None if mentions else _cache_key(text, history)
    hit = _cached(key) if key else None
    if hit:
        citations = json.loads(hit.sources or "[]")
        yield sse({"type": "status", "text": "Same question as before — returning the saved answer"})
        yield sse({"type": "sources", "items": citations})
        yield sse({"type": "token", "text": hit.answer})
        _save_message(session_id, "assistant", hit.answer, payload=json.dumps({"sources": citations, "cached": True}))
        return

    yield sse({"type": "status", "text": "Searching your notes…"})
    queries = build_queries(text, history)
    hits, similarity = index.search_scored(queries, k=6)
    mention_ctx = ""
    if mentions:
        from .notes import mention_context
        mention_ctx = mention_context(mentions)

    off_topic = not hits or similarity < MIN_SIMILARITY
    if not off_topic and not mention_ctx and similarity < CONFIDENT_SIMILARITY:
        yield sse({"type": "status", "text": "Checking your book covers this…"})
        off_topic = not _covered(text, queries, hits)
    if off_topic and not mention_ctx:
        # nothing in the book is about this question: don't let the model answer from its own knowledge
        yield sse({"type": "sources", "items": []})
        yield sse({"type": "token", "text": NOT_IN_BOOK})
        _save_message(session_id, "assistant", NOT_IN_BOOK, payload=json.dumps({"sources": []}))
        if key:
            _store(key, text, NOT_IN_BOOK, [])
        return

    citations = json.loads(citations_json(hits))
    yield sse({"type": "sources", "items": citations})
    system = STUDY_SYSTEM + "\n\nNOTES:\n" + (format_context(hits) if hits else "(no matching notes found)")
    if mention_ctx:
        system += ("\n\nWORKSPACE NOTES Yahia @mentioned (his own pages; use them first and refer to them by "
                   "name, not by number):\n" + mention_ctx)
    messages = history[-8:] + [{"role": "user", "content": text + TURN_REMINDER}]
    answer = []
    for tok in llm.stream_chat(messages, system=system, temperature=0.2):
        answer.append(tok)
        yield sse({"type": "token", "text": tok})
    final = "".join(answer).strip()
    if NOT_IN_BOOK.split(" —")[0].lower() in final.lower()[:40]:
        final, citations = NOT_IN_BOOK, []        # a "don't know" answer should not show unrelated sources
    _save_message(session_id, "assistant", final, payload=json.dumps({"sources": citations}))
    if key and final:
        _store(key, text, final, citations)


def _parse_quiz_args(text: str) -> tuple[int, str]:
    rest = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
    m = re.match(r"^(\d+)\s*(.*)", rest)
    n = min(max(int(m.group(1)), 1), 10) if m else 5
    topic = (m.group(2) if m else rest).strip()
    return n, topic


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------

QUIZ_SYSTEM = """You write exam questions to test a student on THEIR OWN NOTES (the excerpts below).
Mix question types: about 60% multiple choice (4 options, exactly one correct, plausible distractors) and 40% short
answer. Test understanding, not trivia. Each question must be answerable from the excerpts.
Write in English. The student never sees the excerpt numbers, so explanations must not mention excerpts or [n].
Return JSON: {"questions": [
  {"type": "mcq", "question": "...", "options": ["A", "B", "C", "D"], "answer_index": 0,
   "explanation": "why", "source": <excerpt number>, "topic": "short topic"},
  {"type": "short", "question": "...", "answer": "model answer", "explanation": "key points",
   "source": <excerpt number>, "topic": "short topic"}]}"""


def generate_quiz(session_id: int, topic: str, n: int, history: list[dict]) -> list[dict]:
    if topic:
        hits = index.search(build_queries(topic, []), k=8)
    else:
        recent = " ".join(m["content"] for m in history if m["role"] == "user")[-1500:]
        hits = index.search([recent], k=8) if recent.strip() else index.random_chunks(8)
    if not hits:
        raise RuntimeError("No notes are indexed yet — add documents in the Library first")
    data = llm.chat_json(QUIZ_SYSTEM, f"Write {n} questions" + (f" about: {topic}" if topic else "") +
                         f".\n\nEXCERPTS:\n{format_context(hits)}", temperature=0.5)
    items = []
    with session_scope() as s:
        for q in data.get("questions", [])[:n]:
            src_n = q.get("source")
            hit: Hit | None = hits[src_n - 1] if isinstance(src_n, int) and 0 < src_n <= len(hits) else None
            is_mcq = q.get("type") == "mcq" and isinstance(q.get("options"), list) and len(q["options"]) >= 2
            item = QuizItem(session_id=session_id, topic=q.get("topic", topic)[:80], qtype="mcq" if is_mcq else "short",
                            question=q.get("question", ""),
                            options=json.dumps(q.get("options", []) if is_mcq else []),
                            answer=str(q.get("answer_index", 0)) if is_mcq else q.get("answer", ""),
                            explanation=q.get("explanation", ""),
                            source=json.dumps(hit.citation() if hit else {}))
            s.add(item)
            s.commit()
            s.refresh(item)
            items.append(quiz_public(item))
    _save_message(session_id, "assistant", f"Quiz: {len(items)} questions" + (f" on {topic}" if topic else ""),
                  kind="quiz", payload=json.dumps({"ids": [i["id"] for i in items]}))
    return items


def quiz_public(q: QuizItem, reveal: bool = False) -> dict:
    d = {"id": q.id, "type": q.qtype, "question": q.question, "options": json.loads(q.options or "[]"),
         "topic": q.topic, "source": json.loads(q.source or "{}"), "answered": q.user_answer is not None}
    if reveal or q.user_answer is not None:
        d.update({"answer": q.answer, "explanation": q.explanation, "user_answer": q.user_answer,
                  "score": q.score, "feedback": q.feedback})
    return d


GRADE_SYSTEM = """You grade a student's short answers against a model answer. Be fair: accept correct ideas in any
wording or language (English, Arabic, Franco). Return JSON:
{"grades": [{"id": <id>, "score": <0.0-1.0>, "feedback": "one or two sentences: what was right, what was missing"}]}"""


def grade(session_id: int, answers: dict[int, str]) -> list[dict]:
    with session_scope() as s:
        items = {q.id: q for q in s.exec(select(QuizItem).where(QuizItem.session_id == session_id,
                                                                 QuizItem.id.in_(list(answers.keys())))).all()}
        short = []
        for qid, ans in answers.items():
            q = items.get(qid)
            if not q:
                continue
            q.user_answer = str(ans)
            if q.qtype == "mcq":
                q.score = 1.0 if str(ans).strip() == q.answer.strip() else 0.0
                q.feedback = "Correct!" if q.score else "Not quite — see the explanation."
            else:
                short.append(q)
            s.add(q)
        if short:
            payload = [{"id": q.id, "question": q.question, "model_answer": q.answer, "student_answer": q.user_answer}
                       for q in short]
            try:
                data = llm.chat_json(GRADE_SYSTEM, json.dumps(payload, ensure_ascii=False))
                by_id = {int(g["id"]): g for g in data.get("grades", []) if "id" in g}
            except Exception as e:
                log.warning("grading failed: %s", e)
                by_id = {}
            for q in short:
                g = by_id.get(q.id, {})
                q.score = float(max(0.0, min(1.0, g.get("score", 0.0))))
                q.feedback = g.get("feedback", "Could not grade automatically — compare with the model answer.")
                s.add(q)
        s.commit()
        results = [quiz_public(items[qid]) for qid in answers if qid in items]
    total = sum(r["score"] or 0 for r in results)
    _save_message(session_id, "assistant", f"Quiz graded: {total:.1f}/{len(results)}", kind="quiz_result",
                  payload=json.dumps({"ids": [r["id"] for r in results]}))
    return results


# ---------------------------------------------------------------------------
# /end
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM = """You review a finished study session between Yahia and his study assistant, including quiz results.
Be specific and honest; base strengths and weaknesses on evidence (quiz scores, questions he struggled with, topics he
asked about repeatedly). The summary is sent to Yahia himself, so write it in English and address him as "you".
If nothing shows a strength, return an empty strengths list rather than saying so. Return JSON:
{"title": "short session title", "summary": "2-3 sentences", "topics": ["..."],
 "strengths": ["specific strength with evidence"], "weaknesses": ["specific gap with evidence"],
 "study_next": [{"topic": "...", "why": "..."}]}"""


def end_session(session_id: int) -> dict:
    with session_scope() as s:
        msgs = s.exec(select(Message).where(Message.session_id == session_id).order_by(Message.id)).all()
        quiz = s.exec(select(QuizItem).where(QuizItem.session_id == session_id)).all()
        transcript = "\n".join(f"{m.role}: {m.content[:600]}" for m in msgs if m.kind == "text")[-9000:]
        answered = [q for q in quiz if q.score is not None]
        quiz_lines = [f"- [{q.topic}] {q.question} -> score {q.score:.1f}" + (f" ({q.feedback})" if q.feedback else "")
                      for q in answered]
    score = f"{sum(q.score for q in answered):.1f}/{len(answered)}" if answered else "no quiz taken"
    user = f"TRANSCRIPT:\n{transcript or '(empty)'}\n\nQUIZ RESULTS ({score}):\n" + ("\n".join(quiz_lines) or "none")
    data = llm.chat_json(SUMMARY_SYSTEM, user)
    data["score"] = score
    for item in data.get("study_next", [])[:5]:
        hits = index.search([item.get("topic", "")], k=1) if item.get("topic") else []
        if hits:
            h = hits[0]
            item["where"] = f"{h.doc_title} › {h.section}" + (f" (book p. {h.book_page})" if h.book_page else "")
            item["book_page"] = h.book_page
    text = _summary_text(data)
    out = whatsapp.send(text, subject="Study session summary")
    data["whatsapp"] = {"status": out.status, "error": out.error}
    with session_scope() as s:
        sess = s.get(ChatSession, session_id)
        sess.ended_at = datetime.now()
        sess.summary = json.dumps(data, ensure_ascii=False)
        if data.get("title"):
            sess.title = data["title"][:80]
        s.add(sess)
        s.commit()
    _save_message(session_id, "assistant", data.get("summary", ""), kind="summary", payload=json.dumps(data))
    return data


def _summary_text(d: dict) -> str:
    lines = [f"🧠 *Megamind study summary* — {d.get('title', 'Study session')}", "", d.get("summary", ""), "",
             f"📊 Quiz: {d.get('score')}"]
    if d.get("strengths"):
        lines += ["", "💪 *Strengths*"] + [f"• {x}" for x in d["strengths"]]
    if d.get("weaknesses"):
        lines += ["", "⚠️ *Weak spots*"] + [f"• {x}" for x in d["weaknesses"]]
    if d.get("study_next"):
        lines += ["", "📚 *Study next*"]
        for x in d["study_next"]:
            lines.append(f"• {x.get('topic')}: {x.get('why', '')}" + (f"\n   ↳ {x['where']}" if x.get("where") else ""))
    return "\n".join(lines)
