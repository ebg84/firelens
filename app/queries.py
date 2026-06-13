"""Shared parameterized reads used by both the public API and the agent layer.

One place for the composite ZIP read + nearby-fire lookup, so the API endpoint and
the agent's grounding context can't drift. Honest NULLs preserved (NRI-absent /
no-raster ZIPs return None, never 0). No 100%-NULL column is ever selected.
"""
from __future__ import annotations

from . import db

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
