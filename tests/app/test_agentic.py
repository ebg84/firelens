"""3b bounded agentic layer. Deterministic checks on the capped tool set + dispatch
(no API), plus opt-in live golden questions (FIRELENS_LIVE=1) that ASSERT the
no-fabricate behavior and that tools are actually called.
"""
import os

import pytest

from app import agent

LIVE = os.environ.get("FIRELENS_LIVE") == "1"
live_only = pytest.mark.skipif(not LIVE, reason="set FIRELENS_LIVE=1 to run live API tests")


# --- deterministic: the tool set is CAPPED and dispatch is grounded/validated ---

def test_tool_set_is_capped():
    names = {t["name"] for t in agent.TOOLS}
    assert names == {"get_place", "get_fires_near"}  # not open-ended; no free-form SQL tool
    assert agent.AGENT_MAX_ROUNDS == 2
    assert agent.AGENT_MODEL == "claude-opus-4-8"


def test_dispatch_get_place():
    out = agent._dispatch_tool("get_place", {"zip": "95404"})
    assert out["matrix"]["quadrant"] == "harden"


def test_dispatch_get_place_unknown_and_invalid():
    assert "error" in agent._dispatch_tool("get_place", {"zip": "99999"})
    assert "error" in agent._dispatch_tool("get_place", {"zip": "abc"})
    assert "error" in agent._dispatch_tool("get_place", {"zip": ""})


def test_dispatch_get_fires_near_grounded():
    out = agent._dispatch_tool("get_fires_near", {"zip": "95404", "radius_km": 50})
    fires = out["fires"]
    assert len(fires) >= 1
    for f in fires:
        assert "structures_destroyed" not in f and "erc_pctile" not in f  # never the NULL columns


# --- live golden questions (opt-in; real Opus multi-call) ---

@live_only
def test_live_has_it_burned_calls_fires_tool():
    r = agent.agentic("Has the area around here burned before?", focus_zip="95404")
    assert r["degraded"] is False
    assert any(c["name"] == "get_fires_near" for c in r["tool_calls"])  # actually investigated
    assert len(r["answer"]) > 40


@live_only
def test_live_structures_not_fabricated():
    r = agent.agentic("How many structures did the Tubbs fire destroy?", focus_zip="95404")
    a = r["answer"].lower()
    assert any(s in a for s in ("doesn't carry", "don't have", "no data", "not in", "isn't in"))
