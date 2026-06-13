"""FireLens interpretation engine (3a — interpreter / single-shot).

Server gathers the grounded data (place + nearby fires) for a ZIP and hands it to
Claude as TOOL RESULTS with the AGENT.md system prompt. Claude composes a
decision-oriented read citing ONLY those figures. The agentic tool-use loop (3b)
will replace the server-side gather with Claude-driven tool calls.
"""
from __future__ import annotations

import json
import os

import anthropic
from dotenv import load_dotenv

from . import db, queries

load_dotenv()

# Model routing by TASK TYPE (config constants; no runtime classifier):
#   interpreter path (/api/ask single-ZIP, latency-sensitive) -> Sonnet 4.6 (fast, capable
#     for grounded translation)
#   agentic path (3b tool-use loop, multi-ZIP, free-form investigation) -> Opus 4.8
#     (heavier reasoning + the Opus-use score)
# Dynamic auto-routing / model-fallback-on-timeout is deferred to roadmap — the by-endpoint
# split plus graceful degradation is the right robustness for today.
INTERPRETER_MODEL = os.environ.get("FIRELENS_INTERPRETER_MODEL", "claude-sonnet-4-6")
AGENT_MODEL = os.environ.get("FIRELENS_AGENT_MODEL", "claude-opus-4-8")  # 3b agentic path
MAX_TOKENS = 400          # citizen reads are short; tight cap = faster + far less timeout risk
TIMEOUT_S = 60.0

# Shown when the model call fails entirely — the data panels still render, so the page
# degrades to "the narrative didn't load," never a broken page.
FALLBACK_ANSWER = (
    "The interpretation didn't load just now, but the figures below are live: the "
    "hazard×exposure quadrant, the 1940–2026 trend, the fuel substrate, and the built "
    "exposure for this ZIP are all shown and sourced. Try asking again in a moment."
)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # explicit timeout + SDK retries: robust to flaky wifi / transient drops
        _client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=2)
    return _client


def _stream_text(client: anthropic.Anthropic, model: str, system: str, user: str) -> str:
    """Stream the completion and accumulate — progressive receipt avoids a single
    long-held request timing out, and powers the progressive-text UI."""
    chunks: list[str] = []
    with client.messages.stream(
        model=model, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)
    return "".join(chunks).strip()


def _system_prompt() -> str:
    """The verbatim prompt block from docs/AGENT.md (between the first two '---')."""
    text = (db.REPO_ROOT / "docs" / "AGENT.md").read_text()
    parts = text.split("\n---\n")
    if len(parts) >= 2 and len(parts[1].strip()) > 200:
        return parts[1].strip()
    raise RuntimeError("could not parse the system prompt block from docs/AGENT.md")


DEFAULT_QUESTION = (
    "Give a grounded, decision-oriented read of this location: where it sits in the "
    "hazard×exposure matrix and what that implies for action, the atmospheric trend, "
    "the fuel substrate, and the most relevant documented fire nearby. Keep it to 3–4 "
    "tight, plain-language sentences."
)


def _format_user(context: dict, question: str) -> str:
    return (
        "TOOL RESULTS — the ONLY facts you may cite. Any field that is null/None is "
        '"no data": say so, never supply a number.\n\n'
        f"get_place('{context['zip']}') = {json.dumps(context['place'], default=str)}\n\n"
        f"get_fires_near('{context['zip']}') = {json.dumps(context['nearby_fires'], default=str)}\n\n"
        f"served_metrics = {context['served_metrics']} "
        f"(baseline era {context['baseline_era']} vs recent era {context['recent_era']})\n\n"
        f"USER QUESTION: {question}"
    )


def build_context(zip_code: str) -> dict | None:
    place = queries.place_payload(zip_code)
    if place is None:
        return None
    return {
        "zip": zip_code,
        "place": place,
        "nearby_fires": queries.nearby_fires(zip_code),
        "served_metrics": db.served_metrics(),
        "baseline_era": db.BASELINE_ERA,
        "recent_era": db.RECENT_ERA,
    }


def _citations(zip_code: str) -> dict:
    return {"place": f"/api/place/{zip_code}", "trends": f"/api/trends/{zip_code}"}


def interpret(zip_code: str, question: str | None = None) -> dict | None:
    """Grounded interpretation for a ZIP (streams internally, returns the full text).
    None if the ZIP isn't served; a degraded fallback dict if the model call fails."""
    context = build_context(zip_code)
    if context is None:
        return None
    user = _format_user(context, question or DEFAULT_QUESTION)
    system = _system_prompt()
    client = _get_client()
    try:
        answer = _stream_text(client, INTERPRETER_MODEL, system, user)
        return {
            "zip": zip_code, "question": question, "answer": answer,
            "model": INTERPRETER_MODEL, "degraded": False,
            "citations": _citations(zip_code), "context": context,
        }
    except (anthropic.APITimeoutError, anthropic.APIConnectionError, anthropic.APIStatusError):
        return {
            "zip": zip_code, "question": question, "answer": FALLBACK_ANSWER,
            "model": None, "degraded": True,
            "citations": _citations(zip_code), "context": context,
        }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def stream_events(zip_code: str, question: str | None = None):
    """SSE generator: a meta event, progressive text deltas, then done. Degrades to the
    fallback text on any model error — the connection never 500s mid-stream."""
    context = build_context(zip_code)
    if context is None:
        yield _sse("error", {"detail": "unknown zip"})
        return
    user = _format_user(context, question or DEFAULT_QUESTION)
    system = _system_prompt()
    client = _get_client()
    yield _sse("meta", {"zip": zip_code, "citations": _citations(zip_code)})
    try:
        with client.messages.stream(
            model=INTERPRETER_MODEL, max_tokens=MAX_TOKENS, system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            for text in stream.text_stream:
                yield _sse("delta", {"text": text})
        yield _sse("done", {"model": INTERPRETER_MODEL, "degraded": False})
    except (anthropic.APITimeoutError, anthropic.APIConnectionError, anthropic.APIStatusError):
        yield _sse("delta", {"text": FALLBACK_ANSWER})
        yield _sse("done", {"model": None, "degraded": True})
