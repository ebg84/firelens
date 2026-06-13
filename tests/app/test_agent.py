"""Interpretation-engine tests. Deterministic grounding checks (no API calls) +
opt-in live golden questions (set FIRELENS_LIVE=1). The deterministic set enforces
the no-fabricate contract at the context layer, where it's cheap and reliable.
"""
import os

import pytest
from fastapi.testclient import TestClient

from app import agent, queries
from app.main import app

LIVE = os.environ.get("FIRELENS_LIVE") == "1"
live_only = pytest.mark.skipif(not LIVE, reason="set FIRELENS_LIVE=1 to run live API tests")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --- deterministic: the grounded context the model is allowed to cite ---

def test_place_payload_quadrant():
    p = queries.place_payload("95404")
    assert p["matrix"]["quadrant"] == "harden"
    assert p["matrix"]["hazard"]["level"] == "low"
    assert p["matrix"]["exposure"]["level"] == "high"


def test_place_payload_unknown_is_none():
    assert queries.place_payload("99999") is None


def test_nearby_fires_grounding():
    fires = queries.nearby_fires("95404", radius_km=50, limit=6)
    assert 1 <= len(fires) <= 6
    assert [f["acres"] for f in fires] == sorted((f["acres"] for f in fires), reverse=True)
    assert all(f["dist_km"] <= 50 for f in fires)
    # the 100%-NULL columns are never surfaced to the model
    for f in fires:
        assert "structures_destroyed" not in f
        assert "erc_pctile" not in f


def test_build_context_shape():
    ctx = agent.build_context("95404")
    assert ctx["served_metrics"] == ["fwi", "season_length", "dc_pctile"]
    assert "place" in ctx and "nearby_fires" in ctx


def test_system_prompt_has_grounding_guard():
    sp = agent._system_prompt().lower()
    assert "no data" in sp
    assert "structures-destroyed is not in firelens data" in sp


def test_format_user_carries_guard_and_data():
    ctx = agent.build_context("95404")
    txt = agent._format_user(ctx, "test?")
    assert "no data" in txt.lower()
    assert "get_place('95404')" in txt
    assert "get_fires_near('95404')" in txt


def test_ask_malformed_returns_422(client):
    assert client.post("/api/ask", json={"zip": "abc"}).status_code == 422


def test_ask_unknown_zip_returns_404(client):
    # 404 resolves before any API call (context is None)
    assert client.post("/api/ask", json={"zip": "99999"}).status_code == 404


# --- live golden questions (opt-in; real API calls) ---

@live_only
def test_live_interpret_is_grounded():
    r = agent.interpret("95404")
    assert r["model"]
    assert "harden" in r["answer"].lower()  # the real quadrant for 95404


@live_only
def test_live_structures_question_refuses_to_fabricate():
    r = agent.interpret("95404", "How many structures did the Tubbs fire destroy?")
    a = r["answer"].lower()
    assert any(s in a for s in ("doesn't carry", "empty", "no data", "not in"))
