"""LLM access: local Ollama by default, optionally any Anthropic Messages-compatible endpoint.

Embeddings always come from Ollama (bge-m3), so retrieval keeps working offline.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Iterator

import httpx
import numpy as np

from .config import get_settings
from .db import get_setting

log = logging.getLogger(__name__)
THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


def _provider() -> str:
    return get_setting("llm_provider", get_settings().llm_provider)


def _chat_model() -> str:
    return get_setting("chat_model", get_settings().chat_model)


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def _ollama_payload(messages, system, temperature, stream, fmt=None):
    s = get_settings()
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    body = {
        "model": _chat_model(),
        "messages": msgs,
        "stream": stream,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": temperature, "num_ctx": s.num_ctx},
    }
    if fmt:
        body["format"] = fmt
    return body


def _ollama_chat(messages, system, temperature, fmt=None) -> str:
    s = get_settings()
    r = httpx.post(f"{s.ollama_url}/api/chat", json=_ollama_payload(messages, system, temperature, False, fmt),
                   timeout=600)
    r.raise_for_status()
    return THINK_RE.sub("", r.json()["message"]["content"])


def _ollama_stream(messages, system, temperature) -> Iterator[str]:
    s = get_settings()
    in_think = False
    with httpx.stream("POST", f"{s.ollama_url}/api/chat",
                      json=_ollama_payload(messages, system, temperature, True), timeout=600) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            tok = data.get("message", {}).get("content", "")
            # Defensive: some models still emit <think> blocks
            if "<think>" in tok:
                in_think = True
            if in_think:
                if "</think>" in tok:
                    in_think = False
                    tok = tok.split("</think>", 1)[1]
                else:
                    continue
            if tok:
                yield tok
            if data.get("done"):
                break


# ---------------------------------------------------------------------------
# Anthropic Messages API (Claude API, or Ollama's /v1/messages compatibility layer)
# ---------------------------------------------------------------------------

def _anthropic_headers():
    s = get_settings()
    return {"x-api-key": get_setting("anthropic_api_key", s.anthropic_api_key),
            "anthropic-version": "2023-06-01", "content-type": "application/json"}


def _anthropic_body(messages, system, temperature, stream):
    s = get_settings()
    body = {"model": get_setting("anthropic_model", s.anthropic_model), "max_tokens": 4096,
            "messages": messages, "temperature": temperature, "stream": stream}
    if system:
        body["system"] = system
    return body


def _anthropic_url():
    s = get_settings()
    return get_setting("anthropic_base_url", s.anthropic_base_url).rstrip("/") + "/v1/messages"


def _anthropic_chat(messages, system, temperature) -> str:
    r = httpx.post(_anthropic_url(), headers=_anthropic_headers(),
                   json=_anthropic_body(messages, system, temperature, False), timeout=600)
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")


def _anthropic_stream(messages, system, temperature) -> Iterator[str]:
    with httpx.stream("POST", _anthropic_url(), headers=_anthropic_headers(),
                      json=_anthropic_body(messages, system, temperature, True), timeout=600) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line.startswith("data:"):
                data = json.loads(line[5:].strip() or "{}")
                if data.get("type") == "content_block_delta":
                    yield data.get("delta", {}).get("text", "")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat(messages: list[dict], system: str = "", temperature: float = 0.3) -> str:
    if _provider() == "anthropic":
        return _anthropic_chat(messages, system, temperature)
    return _ollama_chat(messages, system, temperature)


def stream_chat(messages: list[dict], system: str = "", temperature: float = 0.3) -> Iterator[str]:
    if _provider() == "anthropic":
        yield from _anthropic_stream(messages, system, temperature)
    else:
        yield from _ollama_stream(messages, system, temperature)


def _extract_json(text: str):
    text = THINK_RE.sub("", text).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}|\[.*\]", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def chat_json(system: str, user: str, temperature: float = 0.2):
    """Ask for a JSON answer and parse it (one retry on malformed output)."""
    messages = [{"role": "user", "content": user}]
    for attempt in range(2):
        if _provider() == "anthropic":
            raw = _anthropic_chat(messages, system + "\nRespond with valid JSON only.", temperature)
        else:
            raw = _ollama_chat(messages, system, temperature, fmt="json")
        try:
            return _extract_json(raw)
        except Exception:
            log.warning("invalid JSON from model (attempt %d): %s", attempt + 1, raw[:300])
    raise ValueError("model did not return valid JSON")


def embed(texts: list[str]) -> np.ndarray:
    s = get_settings()
    out = []
    for i in range(0, len(texts), 16):
        r = httpx.post(f"{s.ollama_url}/api/embed",
                       json={"model": s.embed_model, "input": texts[i:i + 16], "keep_alive": "30m"}, timeout=600)
        r.raise_for_status()
        out.extend(r.json()["embeddings"])
    arr = np.asarray(out, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.clip(norms, 1e-8, None)


def status() -> dict:
    s = get_settings()
    info = {"provider": _provider(), "chat_model": _chat_model(), "embed_model": s.embed_model, "ollama": False,
            "models": []}
    try:
        r = httpx.get(f"{s.ollama_url}/api/tags", timeout=3)
        info["ollama"] = r.status_code == 200
        info["models"] = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return info
