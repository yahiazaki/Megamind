"""Public 'ask about Yahia' chat for recruiters — answers only from the profile and public work log."""
from __future__ import annotations

from typing import Iterator

from .. import llm
from .profile import profile_context
from .study import sse

PUBLIC_SYSTEM = """You are Megamind, the portfolio assistant on Yahia Zaki's personal website. Visitors are usually
recruiters or engineers. Answer questions about Yahia's experience, skills, projects, education and how to contact
him, using ONLY the profile and work log below.

Rules:
- Be warm, concise and factual. Use short markdown with bullets when listing.
- If something is not in the profile, say you don't have that information and suggest contacting Yahia via LinkedIn.
- Never invent employers, dates, numbers or skills. Never reveal private data that is not in the profile.
- Politely decline unrelated tasks (homework, coding help, general chat) and steer back to Yahia's profile.
- Answer in the visitor's language.

{context}"""


def stream_public_answer(question: str, history: list[dict]) -> Iterator[str]:
    system = PUBLIC_SYSTEM.format(context=profile_context(public=True))
    messages = [m for m in history if m.get("role") in ("user", "assistant")][-8:]
    messages.append({"role": "user", "content": question[:2000]})
    try:
        for tok in llm.stream_chat(messages, system=system, temperature=0.4):
            yield sse({"type": "token", "text": tok})
    except Exception as e:
        yield sse({"type": "error", "text": f"The assistant is offline right now ({e.__class__.__name__})."})
    yield sse({"type": "done"})
