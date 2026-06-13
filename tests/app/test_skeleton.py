"""Tier 4 app-integration: skeleton gates (health + trends), gated on REAL
firelens.duckdb values, not fixtures. Using TestClient as a context manager
runs the lifespan, so these also prove startup contract validation succeeds.
"""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

# Real zip_serving values for 95404 (Santa Rosa / Sonoma 06097), read live from
# the DB at build time — the test fails loud if the data layer shifts under us.
ZIP_95404 = {
    "county_fips": "06097",
    "fwi_baseline": 18.977161877773998,
    "fwi_recent": 19.4076376249846,
    "season_length_recent": 159.71963131964984,
    "dc_pctile_recent": 1241.8062564824797,
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # context manager triggers lifespan -> validate_contract()
        yield c


def test_contract_validates():
    summary = db.validate_contract()
    assert summary["tables_validated"] == 10
    assert summary["served_metrics"] == ["fwi", "season_length", "dc_pctile"]


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["tables"] == 10
    assert j["served_metrics"] == ["fwi", "season_length", "dc_pctile"]


def test_trends_95404_real_values(client):
    r = client.get("/api/trends/95404")
    assert r.status_code == 200
    j = r.json()
    assert j["zip"] == "95404"
    assert j["location"]["county_fips"] == ZIP_95404["county_fips"]
    assert set(j["metrics"]) == {"fwi", "season_length", "dc_pctile"}
    assert j["metrics"]["fwi"]["recent"] == pytest.approx(ZIP_95404["fwi_recent"])
    assert j["metrics"]["fwi"]["baseline"] == pytest.approx(ZIP_95404["fwi_baseline"])
    assert j["metrics"]["season_length"]["recent"] == pytest.approx(
        ZIP_95404["season_length_recent"]
    )
    assert j["metrics"]["dc_pctile"]["recent"] == pytest.approx(ZIP_95404["dc_pctile_recent"])


def test_pending_metrics_not_served(client):
    """B1: vpd/cdd/dry_wind_days are pending and must never appear in a response."""
    j = client.get("/api/trends/95404").json()
    for pending in ("vpd", "cdd", "dry_wind_days"):
        assert pending not in j["metrics"]
    assert j["served_metrics"] == ["fwi", "season_length", "dc_pctile"]


def test_robust_not_asserted(client):
    """D1: robust is 100% NULL; the API must not assert a robustness flag."""
    body = client.get("/api/trends/95404").text.lower()
    assert "robust" not in body


def test_unknown_zip_returns_404(client):
    r = client.get("/api/trends/99999")
    assert r.status_code == 404


def test_malformed_zip_returns_422(client):
    assert client.get("/api/trends/abc").status_code == 422
    assert client.get("/api/trends/954").status_code == 422


# --- /api/place: the decision-tool composite read ---

def test_place_95404_quadrant_and_axes(client):
    j = client.get("/api/place/95404").json()
    m = j["matrix"]
    assert m["available"] is True
    assert m["quadrant"] == "harden"  # documented mean-vs-tail case (Tubbs city)
    assert m["hazard"]["level"] == "low"
    assert m["exposure"]["level"] == "high"
    assert m["exposure"]["wfir_ealt"] == pytest.approx(838961.9473308328)
    assert set(j["trends"]["metrics"]) == {"fwi", "season_length", "dc_pctile"}
    assert j["fuel"]["available"] is True


def test_place_nri_absent_is_honest_null(client):
    """NRI-absent ZIP: no quadrant, exposure unavailable — never zero-filled."""
    j = client.get("/api/place/90052").json()
    assert j["matrix"]["available"] is False
    assert j["matrix"]["quadrant"] is None
    assert j["nri"]["available"] is False
    assert j["nri"]["wfir_ealt"] is None


def test_place_fuel_undefined_is_honest_null(client):
    """No-raster ZIP: fuel unavailable, dominant_class NULL (sidesteps the c-e mislabel)."""
    j = client.get("/api/place/96011").json()
    assert j["fuel"]["available"] is False
    assert j["fuel"]["dominant_class"] is None
    assert j["fuel"]["burnable_frac"] is None


def test_place_unknown_and_malformed(client):
    assert client.get("/api/place/99999").status_code == 404
    assert client.get("/api/place/abc").status_code == 422


def test_index_and_static_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200


# --- /explore map layer (degrades gracefully: polygons -> centroids) ---

def test_explore_served(client):
    assert client.get("/explore").status_code == 200
    assert client.get("/static/explore.js").status_code == 200


def test_geo_centroids_fallback(client):
    pts = client.get("/api/geo/centroids").json()["points"]
    assert len(pts) == 1801
    assert all({"zip", "lat", "lon", "quadrant"} <= set(p) for p in pts)
    assert any(p["quadrant"] is None for p in pts)  # NRI-absent stay null, not fabricated


def test_geo_zcta_polygons_or_graceful_404(client):
    r = client.get("/api/geo/zcta")
    assert r.status_code in (200, 404)  # 404 before staging -> frontend uses centroids
    if r.status_code == 200:
        fc = r.json()
        assert fc["type"] == "FeatureCollection"
        assert all("zip" in f["properties"] for f in fc["features"])
