"""/api/methodology — the auditability capstone. Assert the text matches the VERIFIED
derivations (canonical FWI ingested, EFFIS thresholds, FEMA cited, quadrant = ours) —
no overclaim (we didn't compute FWI), no underclaim (it's not a 'proxy').
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def by_key(metrics):
    return {m["key"]: m for m in metrics}


def test_methodology_shape(client):
    d = client.get("/api/methodology").json()
    assert "framing" in d and len(d["metrics"]) == 7
    assert all({"name", "meaning", "derivation", "source", "grain", "time_range", "basis"} <= set(m)
               for m in d["metrics"])
    assert len(d["contract"]) == 11  # live metric_domains carried in


def test_fwi_canonical_ingested_not_proxy(client):
    m = by_key(client.get("/api/methodology").json()["metrics"])["fwi"]
    text = (m["derivation"] + " " + m["source"]).lower()
    assert "canonical" in text and "van wagner" in text and "geff" in text
    assert "ingests" in text or "ingested" in m["basis"]
    assert "does not compute" in text          # no overclaim
    assert "proxy" not in text and "simplified" not in text  # no underclaim


def test_thresholds_are_real(client):
    mm = by_key(client.get("/api/methodology").json()["metrics"])
    assert "21.3" in mm["season_length"]["derivation"]
    assert "38.0" in mm["extreme_days"]["derivation"]


def test_nri_cited_not_computed(client):
    m = by_key(client.get("/api/methodology").json()["metrics"])["nri_ealt"]
    assert m["basis"] == "cited"
    assert "cites" in m["derivation"].lower() and "v1.20" in m["source"]


def test_quadrant_is_ours(client):
    m = by_key(client.get("/api/methodology").json()["metrics"])["quadrant"]
    assert m["basis"] == "constructed"
    assert "not an external standard" in m["derivation"].lower()


def test_methods_page_served(client):
    assert client.get("/methods").status_code == 200
    assert client.get("/static/methods.js").status_code == 200
