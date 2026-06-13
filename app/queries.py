"""Shared parameterized reads used by both the public API and the agent layer.

One place for the composite ZIP read + nearby-fire lookup, so the API endpoint and
the agent's grounding context can't drift. Honest NULLs preserved (NRI-absent /
no-raster ZIPs return None, never 0). No 100%-NULL column is ever selected.
"""
from __future__ import annotations

import re

from . import counties, db

FUEL_FRACTIONS = [
    "grass_frac", "grass_shrub_frac", "shrub_frac",
    "timber_understory_frac", "timber_litter_frac", "slash_blowdown_frac",
]
# quadrant -> (hazard level, exposure level); median split, hazard axis = recent mean FWI
QUADRANT_AXES = {
    "priority": ("high", "high"),
    "monitor": ("high", "low"),
    "harden": ("low", "high"),
    "low_priority": ("low", "low"),
}

_medians: tuple | None = None


def matrix_medians() -> tuple:
    global _medians
    if _medians is None:
        _medians = db.query_one(
            "select median(fwi_level), median(wfir_ealt) from zip_priority_matrix"
        )
    return _medians


def place_payload(zip_code: str) -> dict | None:
    """Composite decision read for a ZIP, or None if not in the serving layer."""
    metrics = db.served_metrics()
    trend_cols: list[str] = []
    for m in metrics:
        trend_cols += [f"{m}_baseline", f"{m}_recent", f"{m}_pct_change", f"{m}_freq_ratio"]
    base_cols = [
        "lat", "lon", "county_fips", "quadrant",
        "wfir_risks", "wfir_afreq", "wfir_ealt", "nri_n_tracts",
        "burnable_frac", "non_burnable_frac", "dominant_class",
    ] + FUEL_FRACTIONS
    cols = base_cols + trend_cols
    select = ", ".join(f's."{c}"' for c in cols)
    row = db.query_one(
        f"select {select}, m.fwi_level from zip_serving s "
        f"left join zip_priority_matrix m on s.zip = m.zip where s.zip = ?",
        [zip_code],
    )
    if row is None:
        return None
    d = dict(zip(cols + ["fwi_level"], row))
    haz_med, exp_med = matrix_medians()
    quadrant = d["quadrant"]
    haz_level, exp_level = QUADRANT_AXES.get(quadrant, (None, None))
    nri_available = d["wfir_ealt"] is not None
    fuel_available = d["burnable_frac"] is not None

    return {
        "location": {"lat": d["lat"], "lon": d["lon"], "county_fips": d["county_fips"]},
        "matrix": {
            "available": quadrant is not None,
            "quadrant": quadrant,
            "hazard": {"fwi_level": d["fwi_level"], "median": haz_med, "level": haz_level},
            "exposure": {"wfir_ealt": d["wfir_ealt"], "median": exp_med, "level": exp_level},
            "note": "Hazard axis = recent-era MEAN FWI, split at the statewide median; "
            "extreme-day tails live in the trend panel.",
        },
        "trends": {
            "baseline_era": db.BASELINE_ERA,
            "recent_era": db.RECENT_ERA,
            "metrics": {
                m: {
                    "baseline": d[f"{m}_baseline"],
                    "recent": d[f"{m}_recent"],
                    "pct_change": d[f"{m}_pct_change"],
                    "freq_ratio": d[f"{m}_freq_ratio"],
                }
                for m in metrics
            },
        },
        "fuel": {
            "available": fuel_available,
            "burnable_frac": d["burnable_frac"],
            "dominant_class": d["dominant_class"] if fuel_available else None,
            "composition": (
                {f.replace("_frac", ""): d[f] for f in FUEL_FRACTIONS}
                if fuel_available
                else None
            ),
        },
        "nri": {
            "available": nri_available,
            "wfir_ealt": d["wfir_ealt"],
            "wfir_risks": d["wfir_risks"],
            "wfir_afreq": d["wfir_afreq"],
            "n_tracts": d["nri_n_tracts"],
        },
    }


def county_zips(county_fips: str) -> list[dict]:
    """Every serving ZIP in a county with its quadrant + centroid (for map navigation)."""
    rows = db.query(
        "select s.zip, s.quadrant, z.lat, z.lon "
        "from zip_serving s join zip_meta z on s.zip = z.zip "
        "where s.county_fips = ? order by s.zip",
        [county_fips],
    )
    return [{"zip": r[0], "quadrant": r[1], "lat": r[2], "lon": r[3]} for r in rows]


def search(q: str) -> dict:
    """Resolve a ZIP, county, or free-text query to real ZIP-grain data.

    A NAVIGATION aid, never a new aggregated metric. ZIP and county resolve from data;
    place/city names are not resolved (no ZIP->place dataset) — never fabricated.
    """
    q = (q or "").strip()
    if not q:
        return {"type": "unresolved", "query": q, "message": "Enter a ZIP code or a county name."}

    if re.fullmatch(r"\d{5}", q):
        resolved = place_payload(q) is not None
        return {
            "type": "zip", "query": q, "resolved": resolved,
            "zip": q if resolved else None,
            "message": None if resolved else f"ZIP {q} is not in the California serving layer.",
        }

    match = counties.resolve_county(q)
    if match:
        name, fips = match
        zips = county_zips(fips)
        dist: dict = {}
        for z in zips:
            key = z["quadrant"] or "no_nri"
            dist[key] = dist.get(key, 0) + 1
        return {
            "type": "county", "query": q, "county": name, "county_fips": fips,
            "count": len(zips), "zips": zips, "distribution": dist,
            "note": "A county is a navigation aid to ZIP-level data — counties hold both "
            "higher- and lower-risk ZIPs, so there is no single county score.",
        }

    candidates = counties.county_candidates(q)
    if len(candidates) == 1:
        return search(candidates[0])  # unambiguous substring -> resolve as that county
    if candidates:
        return {"type": "ambiguous", "query": q, "candidates": candidates,
                "message": "Did you mean one of these counties?"}
    return {
        "type": "unresolved", "query": q,
        "message": "Enter a 5-digit ZIP code or a California county name "
        "(place/city search isn't available yet).",
    }


def cell_series(zip_code: str) -> dict | None:
    """The full-coverage annual fire-weather record (1940-2026) for the grid cell a ZIP
    sits in (its max-weight cell). SPINE-ONLY metrics (fwi_mean, extreme_days, season_len) —
    never fire events / NRI / fuel / pending layers. None if the ZIP isn't served.
    """
    cell = db.query_one(
        "select c.cell_id, c.lat, c.lon, m.weight, z.county_fips "
        "from zip_cell_map m join cell_meta c on m.cell_id = c.cell_id "
        "join zip_meta z on m.zip = z.zip "
        "where m.zip = ? order by m.weight desc limit 1",
        [zip_code],
    )
    if cell is None:
        return None
    cell_id, lat, lon, weight, county_fips = cell
    # The GEFF-ERA5 spine trails into a PARTIAL current year (e.g. mid-2026 reads a half-year
    # annual value — a false collapse). Exclude the trailing year so the chart ends on the last
    # COMPLETE year; all four metrics share the artifact, so one trim fixes them consistently.
    max_year = db.query_one("select max(year) from cell_annual where cell_id = ?", [cell_id])[0]
    complete_through = max_year - 1
    rows = db.query(
        "select year, fwi_mean, extreme_days, season_len, dc_max from cell_annual "
        "where cell_id = ? and year <= ? order by year",
        [cell_id, complete_through],
    )
    first_year = rows[0][0] if rows else None
    return {
        "zip": zip_code,
        "cell_id": cell_id,
        "lat": lat,
        "lon": lon,
        "weight": weight,
        "county_fips": county_fips,
        "metric": "fwi_mean",
        "metrics": ["fwi_mean", "season_len", "dc_max", "extreme_days"],  # all full-coverage spine
        "complete_through": complete_through,
        "partial_year_excluded": max_year,
        "source": f"ERA5-derived fire-weather record, {first_year}-{complete_through}, "
        "the grid cell this ZIP sits in",
        "points": [
            {"year": r[0], "fwi_mean": r[1], "extreme_days": r[2],
             "season_len": r[3], "dc_max": r[4]}
            for r in rows
        ],
    }


def all_fires() -> list[dict]:
    """Every recorded ignition (FOD/FRAP 1992-2025) with point + acres + ignition-day FWI
    percentile — for the map's density overlay. A sample of significant recorded fires, not a census."""
    rows = db.query(
        "select name, ign_date, acres, fwi_pctile, lat, lon from fire_events "
        "where lat is not null and lon is not null"
    )
    return [
        {"name": r[0], "year": (r[1].year if r[1] is not None else None),
         "acres": r[2], "fwi_pctile": r[3], "lat": r[4], "lon": r[5]}
        for r in rows
    ]


def nearby_fires(zip_code: str, radius_km: float = 50.0, limit: int = 6) -> list[dict]:
    """Documented fires near a ZIP (haversine on the ZIP centroid), largest first.

    Selects only populated fire_events columns — never erc_pctile/structures_destroyed.
    fwi_pctile may be NULL (offshore/pre-1992 pairing); the agent reads NULL as no-data.
    """
    z = db.query_one("select lat, lon from zip_meta where zip = ?", [zip_code])
    if z is None:
        return []
    zlat, zlon = z
    rows = db.query(
        """
        select name, ign_date, acres, fwi_pctile, cause_class, source, dist_km from (
          select name, ign_date, acres, fwi_pctile, cause_class, source,
            6371 * 2 * asin(sqrt(
              power(sin(radians(lat - ?) / 2), 2) +
              cos(radians(?)) * cos(radians(lat)) *
              power(sin(radians(lon - ?) / 2), 2))) as dist_km
          from fire_events
        ) where dist_km <= ? order by acres desc limit ?
        """,
        [zlat, zlat, zlon, radius_km, limit],
    )
    return [
        {
            "name": r[0],
            "ign_date": r[1].isoformat() if r[1] is not None else None,
            "acres": r[2],
            "fwi_pctile": r[3],
            "cause_class": r[4],
            "source": r[5],
            "dist_km": round(r[6], 1),
        }
        for r in rows
    ]
