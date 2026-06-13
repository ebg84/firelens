"""/api/search (ZIP + county navigation) and the enriched map-tooltip properties.
Honesty: county is a navigation aid, never an aggregated score; NULLs never become numbers.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_search_zip_resolved(client):
    j = client.get("/api/search", params={"q": "95404"}).json()
    assert j["type"] == "zip" and j["resolved"] is True and j["zip"] == "95404"


def test_search_zip_unresolved(client):
    j = client.get("/api/search", params={"q": "99999"}).json()
    assert j["type"] == "zip" and j["resolved"] is False and j["zip"] is None


def test_search_county_returns_real_zips_not_a_score(client):
    j = client.get("/api/search", params={"q": "Sonoma"}).json()
    assert j["type"] == "county" and j["county"] == "Sonoma"
    assert j["count"] == len(j["zips"]) > 0
    assert all({"zip", "quadrant", "lat", "lon"} <= set(z) for z in j["zips"])
    assert "note" in j  # the navigation-aid disclaimer
    # never a synthesized county metric
    assert "risk_score" not in j and "score" not in j


def test_search_county_suffix(client):
    j = client.get("/api/search", params={"q": "sonoma county"}).json()
    assert j["type"] == "county" and j["county"] == "Sonoma"


def test_search_ambiguous(client):
    j = client.get("/api/search", params={"q": "san"}).json()
    assert j["type"] == "ambiguous" and len(j["candidates"]) > 1


def test_search_unresolved_is_honest(client):
    j = client.get("/api/search", params={"q": "zzzznotaplace"}).json()
    assert j["type"] == "unresolved" and "message" in j


def test_geo_zcta_tooltip_fields(client):
    r = client.get("/api/geo/zcta")
    if r.status_code != 200:
        pytest.skip("geometry not staged")
    feats = r.json()["features"]
    props = feats[0]["properties"]
    # tooltip + viridis coloring fields
    assert {"zip", "quadrant", "county_fips", "fwi_pct_change",
            "fwi_recent", "extreme_recent", "wfir_ealt"} <= set(props)
    # honest NULLs: continuous spine metrics fully populated; NRI exposure null for NRI-absent ZIPs
    assert all(f["properties"]["fwi_recent"] is not None for f in feats)
    assert any(f["properties"]["wfir_ealt"] is None for f in feats)  # -> rendered gray, not a value


def test_geo_centroids_tooltip_fields(client):
    pts = client.get("/api/geo/centroids").json()["points"]
    assert all({"zip", "quadrant", "county_fips", "fwi_pct_change"} <= set(p) for p in pts)
