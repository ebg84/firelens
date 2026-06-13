"""/api/series — the 1940-2026 annual fire-weather record (history, not forecast).
Honesty: full-coverage spine metrics only; never fire-events / static / pending layers.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

SPINE_METRICS = {"fwi_mean", "extreme_days", "season_len", "dc_max"}
FORBIDDEN = {"quadrant", "wfir_ealt", "fires", "burnable_frac", "vpd", "cdd", "structures_destroyed"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_series_full_span(client):
    s = client.get("/api/series/95404").json()
    years = [p["year"] for p in s["points"]]
    assert years[0] == 1940 and years[-1] == 2026
    assert len(years) == 87  # full 1940-2026 depth, no truncation
    assert years == sorted(years)


def test_series_all_four_spine_metrics(client):
    s = client.get("/api/series/95404").json()
    assert set(s["metrics"]) == SPINE_METRICS
    for p in s["points"]:
        assert SPINE_METRICS <= set(p)            # every metric present every year (full coverage)
        assert all(p[m] is not None for m in SPINE_METRICS)  # no back-fill / no gaps


def test_series_plots_only_spine_no_forbidden_layers(client):
    s = client.get("/api/series/95404").json()
    blob = str(s).lower()
    for bad in FORBIDDEN:
        assert bad not in str(s["points"]).lower()
    # the source is labeled as the grid cell, full range
    assert "1940-2026" in s["source"] and "grid cell" in s["source"].lower()


def test_series_unknown_and_malformed(client):
    assert client.get("/api/series/99999").status_code == 404
    assert client.get("/api/series/abc").status_code == 422
