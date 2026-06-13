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


# --- 3b: bounded agentic layer (Opus 4.8, capped tools, max 2 tool rounds) ---

AGENT_MAX_ROUNDS = 2
AGENT_MAX_TOKENS = 600
# The SYNC (non-stream) agentic path fails FAST to the Sonnet fallback — a hung Opus call
# must not stall a demo (the old 60s x 2-retry x rounds = ~197s). The STREAMING product path
# (agent_stream) keeps the normal client, since streaming receives progressively and is robust.
AGENT_SYNC_TIMEOUT = 20.0
AGENT_SYNC_RETRIES = 0

TOOLS = [
    {
        "name": "get_place",
        "description": "Grounded decision data for a California ZIP: the hazard×exposure "
        "quadrant, era trends (fwi, season_length, dc_pctile; baseline 1980-2000 vs recent "
        "2010-present), fuel composition, and FEMA NRI built exposure. A null field means NO "
        "DATA — never invent a value for it.",
        "input_schema": {
            "type": "object",
            "properties": {"zip": {"type": "string", "description": "5-digit California ZIP"}},
            "required": ["zip"],
        },
    },
    {
        "name": "get_fires_near",
        "description": "Documented fires near a California ZIP (FPA-FOD 1992-2020 + FRAP 2021+), "
        "largest first, each with ignition-day FWI percentile, acreage, cause, distance. Use for "
        "'has it burned before'. An empty list means none on record within the radius.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zip": {"type": "string", "description": "5-digit California ZIP"},
                "radius_km": {"type": "number", "description": "search radius in km (default 50)"},
            },
            "required": ["zip"],
        },
    },
]

AGENT_TOOL_NOTE = (
    "\n\n## Your tools (bounded)\nYou have exactly two tools: get_place(zip) and "
    "get_fires_near(zip, radius_km). Call them to ground every figure; use at most two rounds "
    "of tool calls, then answer. Cite only what they return — null fields are 'no data'. Scope: "
    "is-my-area-at-risk, why/what-drives-it, has-it-burned-before, compare-nearby."
)


def _dispatch_tool(name: str, inp: dict) -> dict:
    """Run a capped tool against the real query functions. Input-validated; never free SQL."""
    zip_code = str(inp.get("zip", "")).strip()
    if not (len(zip_code) == 5 and zip_code.isdigit()):
        return {"error": f"invalid zip {zip_code!r}; must be 5 digits"}
    if name == "get_place":
        return queries.place_payload(zip_code) or {
            "error": f"ZIP {zip_code} not in the California serving layer"
        }
    if name == "get_fires_near":
        radius = float(inp.get("radius_km") or 50)
        return {"zip": zip_code, "fires": queries.nearby_fires(zip_code, radius_km=radius)}
    return {"error": f"unknown tool {name}"}


def _agent_messages(question: str, focus_zip: str | None) -> list:
    prefix = f"(Focus ZIP: {focus_zip}.) " if focus_zip else ""
    return [{"role": "user", "content": prefix + question}]


def agentic(question: str, focus_zip: str | None = None) -> dict:
    """Non-streaming bounded agentic loop (tests + fallback shape).
    Returns {answer, model, tool_calls, degraded}."""
    client = _get_client().with_options(timeout=AGENT_SYNC_TIMEOUT, max_retries=AGENT_SYNC_RETRIES)
    system = _system_prompt() + AGENT_TOOL_NOTE
    messages = _agent_messages(question, focus_zip)
    tool_calls: list = []
    try:
        for _round in range(AGENT_MAX_ROUNDS):
            resp = client.messages.create(
                model=AGENT_MODEL, max_tokens=AGENT_MAX_TOKENS, system=system,
                tools=TOOLS, messages=messages,
            )
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                text = "".join(b.text for b in resp.content if b.type == "text").strip()
                return {"answer": text, "model": AGENT_MODEL, "tool_calls": tool_calls, "degraded": False}
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    tool_calls.append({"name": b.name, "input": b.input})
                    out = _dispatch_tool(b.name, b.input)
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": json.dumps(out, default=str)})
            messages.append({"role": "user", "content": results})
        # rounds exhausted still wanting tools -> force a final answer with no tools
        resp = client.messages.create(
            model=AGENT_MODEL, max_tokens=AGENT_MAX_TOKENS, system=system, messages=messages,
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return {"answer": text, "model": AGENT_MODEL, "tool_calls": tool_calls, "degraded": False}
    except (anthropic.APITimeoutError, anthropic.APIConnectionError, anthropic.APIStatusError):
        if focus_zip:  # graceful degradation to the fast Sonnet interpreter
            fb = interpret(focus_zip, question)
            if fb:
                return {"answer": fb["answer"], "model": fb["model"],
                        "tool_calls": tool_calls, "degraded": True}
        return {"answer": FALLBACK_ANSWER, "model": None, "tool_calls": tool_calls, "degraded": True}


def agent_stream(question: str, focus_zip: str | None = None):
    """SSE: emit a 'tool' event per call (investigation made visible), stream the final
    answer's deltas. Falls back to the Sonnet interpreter if the loop errors."""
    client = _get_client()
    system = _system_prompt() + AGENT_TOOL_NOTE
    messages = _agent_messages(question, focus_zip)
    yield _sse("meta", {"focus_zip": focus_zip, "model": AGENT_MODEL})
    try:
        for _round in range(AGENT_MAX_ROUNDS):
            with client.messages.stream(
                model=AGENT_MODEL, max_tokens=AGENT_MAX_TOKENS, system=system,
                tools=TOOLS, messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield _sse("delta", {"text": text})
                final = stream.get_final_message()
            messages.append({"role": "assistant", "content": final.content})
            if final.stop_reason != "tool_use":
                yield _sse("done", {"model": AGENT_MODEL, "degraded": False})
                return
            results = []
            for b in final.content:
                if b.type == "tool_use":
                    yield _sse("tool", {"name": b.name, "input": b.input})
                    out = _dispatch_tool(b.name, b.input)
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": json.dumps(out, default=str)})
            messages.append({"role": "user", "content": results})
        with client.messages.stream(  # forced final answer, no tools
            model=AGENT_MODEL, max_tokens=AGENT_MAX_TOKENS, system=system, messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield _sse("delta", {"text": text})
        yield _sse("done", {"model": AGENT_MODEL, "degraded": False})
    except (anthropic.APITimeoutError, anthropic.APIConnectionError, anthropic.APIStatusError):
        if focus_zip:
            fb = interpret(focus_zip, question)
            if fb:
                yield _sse("delta", {"text": fb["answer"]})
                yield _sse("done", {"model": fb["model"], "degraded": True})
                return
        yield _sse("delta", {"text": FALLBACK_ANSWER})
        yield _sse("done", {"model": None, "degraded": True})
