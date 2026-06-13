"""FireLens FastAPI service — skeleton: health + ZIP era-trends.

Every served figure traces to a replayable public URL. The served metric set is
driven by the manifest contract (fwi, season_length, dc_pctile); pending metrics
(vpd/cdd/dry_wind_days) are not served and not exposed here.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, queries

STATIC_DIR = Path(__file__).resolve().parent / "static"
GEO_PATH = db.REPO_ROOT / "data" / "geo" / "ca_zcta.geojson"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fail loud at startup if the DB diverges from the manifest contract.
    db.validate_contract()
    yield


app = FastAPI(
    title="FireLens API",
    version="0.1.0",
    description="California wildfire climate intelligence — descriptive, evidence-cited, "
    "every figure backed by a replayable URL.",
    lifespan=lifespan,
)

# CORS-open for reads (locked arch #9b: the public API is the open substrate).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _valid_zip(zip_code: str) -> bool:
    return len(zip_code) == 5 and zip_code.isdigit()


@app.get("/api/health")
def health() -> dict:
    """Liveness + contract summary. 200 once the DB matches the manifest."""
    mf = db.load_manifest()
    return {
        "status": "ok",
        "manifest_git_hash": mf["build"]["git_hash"],
        "tables": len(mf["tables"]),
        "served_metrics": db.served_metrics(),
    }


@app.get("/api/trends/{zip_code}")
def trends(zip_code: str) -> dict:
    """Era-trend (two eras + delta) per served metric for a California ZIP.

    Reads the `zip_serving` snapshot view. Unknown ZIP -> 404; malformed -> 422.
    """
    if not _valid_zip(zip_code):
        raise HTTPException(status_code=422, detail=f"ZIP must be 5 digits, got {zip_code!r}")

    metrics = db.served_metrics()
    cols = ["lat", "lon", "county_fips"]
    for m in metrics:
        cols += [f"{m}_baseline", f"{m}_recent", f"{m}_pct_change", f"{m}_freq_ratio"]
    select = ", ".join(f'"{c}"' for c in cols)
    row = db.query_one(f"select {select} from zip_serving where zip = ?", [zip_code])
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"ZIP {zip_code} not in the California serving layer"
        )

    data = dict(zip(cols, row))
    return {
        "zip": zip_code,
        "location": {
            "lat": data["lat"],
            "lon": data["lon"],
            "county_fips": data["county_fips"],
        },
        "baseline_era": db.BASELINE_ERA,
        "recent_era": db.RECENT_ERA,
        "metrics": {
            m: {
                "baseline": data[f"{m}_baseline"],
                "recent": data[f"{m}_recent"],
                "pct_change": data[f"{m}_pct_change"],
                "freq_ratio": data[f"{m}_freq_ratio"],
            }
            for m in metrics
        },
        "served_metrics": metrics,
        "source_url": f"/api/trends/{zip_code}",
    }


@app.get("/api/place/{zip_code}")
def place(zip_code: str) -> dict:
    """Composite grounded decision view for a CA ZIP: hazard×exposure quadrant +
    era-trends + fuel + NRI exposure. The decision tool's primary read. Honest NULLs:
    NRI-absent ZIPs carry no quadrant/exposure; no-raster ZIPs carry no fuel.
    """
    if not _valid_zip(zip_code):
        raise HTTPException(status_code=422, detail=f"ZIP must be 5 digits, got {zip_code!r}")
    payload = queries.place_payload(zip_code)
    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"ZIP {zip_code} not in the California serving layer"
        )
    payload["zip"] = zip_code
    payload["served_metrics"] = db.served_metrics()
    payload["matrix"]["source_url"] = f"/api/place/{zip_code}"
    payload["trends"]["source_url"] = f"/api/trends/{zip_code}"
    return payload


class AskRequest(BaseModel):
    zip: str
    question: str | None = None


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    """Interpretation engine (3a): grounded prose for a ZIP, optionally answering a
    question. Cites only the served data; NULLs are 'no data', never a number."""
    if not _valid_zip(req.zip):
        raise HTTPException(status_code=422, detail=f"ZIP must be 5 digits, got {req.zip!r}")
    from . import agent  # lazy import keeps the rest of the API independent of the API key

    result = agent.interpret(req.zip, req.question)
    if result is None:
        raise HTTPException(status_code=404, detail=f"ZIP {req.zip} not in the serving layer")
    return result


@app.get("/api/agent/stream")
def agent_stream_ep(q: str, zip: str | None = None) -> StreamingResponse:
    """Bounded agentic layer (SSE): Opus 4.8 with capped tools (get_place + get_fires_near,
    max 2 rounds) investigates a free-form question, emitting a tool event per call. Falls
    back to the Sonnet interpreter on error."""
    if zip is not None and not _valid_zip(zip):
        raise HTTPException(status_code=422, detail=f"ZIP must be 5 digits, got {zip!r}")
    from . import agent

    return StreamingResponse(
        agent.agent_stream(q, zip),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/ask/stream")
def ask_stream(zip: str, question: str | None = None) -> StreamingResponse:
    """Streaming interpretation (SSE): progressive text deltas — robust to slow/long
    generations and powers the progressive-text UI. Degrades to a fallback, never 500s."""
    if not _valid_zip(zip):
        raise HTTPException(status_code=422, detail=f"ZIP must be 5 digits, got {zip!r}")
    from . import agent

    if agent.build_context(zip) is None:
        raise HTTPException(status_code=404, detail=f"ZIP {zip} not in the serving layer")
    return StreamingResponse(
        agent.stream_events(zip, question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/search")
def search(q: str) -> dict:
    """Resolve a ZIP, county, or free-text query to real ZIP-grain data — a navigation
    aid (people don't know their ZIP), never a new aggregated metric."""
    return queries.search(q)


@app.get("/api/series/{zip_code}")
def series(zip_code: str) -> dict:
    """The full 1940-2026 annual fire-weather record for the grid cell a ZIP sits in —
    the 'history, not forecast' time series. Spine-only (fwi_mean/extreme_days/season_len)."""
    if not _valid_zip(zip_code):
        raise HTTPException(status_code=422, detail=f"ZIP must be 5 digits, got {zip_code!r}")
    s = queries.cell_series(zip_code)
    if s is None:
        raise HTTPException(
            status_code=404, detail=f"ZIP {zip_code} not in the California serving layer"
        )
    return s


# --- map data (the /explore in-tandem evidence surface) ---

_geo_cache: dict | None = None


def _zcta_featurecollection() -> dict | None:
    """CA ZCTA polygons with quadrant/hazard/exposure merged into properties (cached).

    Returns None if the geometry isn't staged — the frontend falls back to centroids.
    """
    global _geo_cache
    if _geo_cache is None:
        if not GEO_PATH.exists():
            return None
        fc = json.loads(GEO_PATH.read_text())
        rows = db.query(
            "select s.zip, s.quadrant, m.fwi_level, s.wfir_ealt, s.county_fips, s.fwi_pct_change "
            "from zip_serving s left join zip_priority_matrix m on s.zip = m.zip"
        )
        meta = {
            r[0]: {
                "quadrant": r[1], "fwi_level": r[2], "wfir_ealt": r[3],
                "county_fips": r[4], "fwi_pct_change": r[5],
            }
            for r in rows
        }
        for feat in fc.get("features", []):
            z = feat.get("properties", {}).get("zip")
            info = meta.get(z, {})
            feat["properties"] = {"zip": z, **info}
        _geo_cache = fc
    return _geo_cache


@app.get("/api/geo/zcta", include_in_schema=False)
def geo_zcta():
    fc = _zcta_featurecollection()
    if fc is None:
        raise HTTPException(status_code=404, detail="ZCTA geometry not staged")
    return JSONResponse(fc)


@app.get("/api/geo/centroids")
def geo_centroids() -> dict:
    """Fallback map layer: ZIP centroids + quadrant from zip_meta (zero external data)."""
    rows = db.query(
        "select s.zip, z.lat, z.lon, s.quadrant, s.county_fips, s.fwi_pct_change "
        "from zip_serving s join zip_meta z on s.zip = z.zip"
    )
    return {
        "points": [
            {
                "zip": r[0], "lat": r[1], "lon": r[2], "quadrant": r[3],
                "county_fips": r[4], "fwi_pct_change": r[5],
            }
            for r in rows
        ]
    }


# Static frontend. The app's "/" route is the analyst/decision input (locked arch #8);
# the map is the in-tandem evidence surface at /explore. "dashboard" appears nowhere by design.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/explore", include_in_schema=False)
def explore() -> FileResponse:
    return FileResponse(STATIC_DIR / "explore.html")
