"""Methodology content — the verified derivations (from prep/metrics.py + docs/DATA.md),
not general fire-science. The trust distinction: FireLens INGESTS canonical indices,
CITES published datasets, and CONSTRUCTS exactly one analytic of its own (the quadrant).
"""

FRAMING = (
    "FireLens computes nothing from raw fire science itself. It INGESTS canonical "
    "fire-danger indices (the Fire Weather Index and Drought Code, computed by ECMWF's GEFF "
    "model from the ERA5 reanalysis), CITES authoritative published datasets (FEMA's National "
    "Risk Index, LANDFIRE fuel models), and CONSTRUCTS exactly one analytic of its own — the "
    "hazard×exposure quadrant. Season-length and extreme-day figures are simple day-counts over "
    "the ingested FWI at published EFFIS thresholds. Every number traces to an open, named source."
)

# basis: "ingested" (canonical index from others) | "derived" (FireLens count over ingested data)
#        | "cited" (published figures used as-is) | "constructed" (FireLens's own analytic)
METHODOLOGY = [
    {
        "key": "fwi",
        "name": "Fire Weather Index",
        "meaning": "How dangerous fire-weather conditions are — heat, wind, and dryness combined.",
        "derivation": "The canonical Canadian Fire Weather Index (Van Wagner 1987), computed by "
        "ECMWF's GEFF model from the ERA5 reanalysis. FireLens ingests the published daily index "
        "— it does not compute or simplify it. We report the annual mean (fwi_mean) and max (fwi_max).",
        "source": "Copernicus CEMS — GEFF-ERA5 (via EWDS); Canadian FWI, Van Wagner 1987",
        "grain": "~31 km grid cell, daily",
        "time_range": "1940–2026",
        "basis": "ingested",
    },
    {
        "key": "dc",
        "name": "Drought Code",
        "meaning": "How dry the deep soil is — a slow-drying signal that drives how intensely fire burns.",
        "derivation": "A component of the same FWI system, from the GEFF-ERA5 record. FireLens "
        "ingests it and reports the annual maximum (dc_max).",
        "source": "Copernicus CEMS — GEFF-ERA5 (FWI-system Drought Code)",
        "grain": "~31 km grid cell, daily",
        "time_range": "1940–2026",
        "basis": "ingested",
    },
    {
        "key": "season_length",
        "name": "Fire-season length",
        "meaning": "How many days a year the weather can carry fire.",
        "derivation": "FireLens counts the days per year with FWI ≥ 21.3 — the EFFIS 'high' "
        "fire-danger lower bound — for the ZIP's grid cell.",
        "source": "FireLens count over the ingested GEFF-ERA5 FWI; threshold per EFFIS fire-danger classes",
        "grain": "~31 km grid cell, annual",
        "time_range": "1940–2026",
        "basis": "derived",
    },
    {
        "key": "extreme_days",
        "name": "Extreme fire-weather days",
        "meaning": "Days per year of extreme fire-weather conditions.",
        "derivation": "FireLens counts the days per year with FWI ≥ 38.0 — the EFFIS 'extreme' "
        "threshold — for the ZIP's grid cell.",
        "source": "FireLens count over the ingested GEFF-ERA5 FWI; threshold per EFFIS",
        "grain": "~31 km grid cell, annual",
        "time_range": "1940–2026",
        "basis": "derived",
    },
    {
        "key": "nri_ealt",
        "name": "FEMA Expected Annual Loss (built exposure)",
        "meaning": "FEMA's estimate of the building value expected to be lost to wildfire each year.",
        "derivation": "FEMA's published Expected Annual Loss to buildings from wildfire. FireLens "
        "cites these figures — it does not model or compute them. Tract-level NRI is mapped to ZIP "
        "via the HUD USPS tract→ZIP crosswalk.",
        "source": "FEMA National Risk Index v1.20 (2025); HUD USPS tract→ZIP crosswalk",
        "grain": "ZIP (from 2020 census tracts), static",
        "time_range": "2025 snapshot",
        "basis": "cited",
    },
    {
        "key": "fuel",
        "name": "Fuel (LANDFIRE FBFM40)",
        "meaning": "What's on the ground to burn — grass, shrub, or timber.",
        "derivation": "LANDFIRE Scott & Burgan 40 fire-behavior fuel models, classified from the "
        "published raster via per-ZIP zonal statistics (burnable fraction + dominant class).",
        "source": "LANDFIRE FBFM40 (LF2025), USGS/USFS",
        "grain": "30 m raster → ZIP (zonal), static",
        "time_range": "current LANDFIRE cycle (LF2025)",
        "basis": "cited",
    },
    {
        "key": "quadrant",
        "name": "Hazard × Exposure quadrant",
        "meaning": "FireLens's own way of separating where the fire-weather hazard is high from "
        "where the built exposure is high.",
        "derivation": "A FireLens analytic: recent-era mean FWI (hazard) × FEMA NRI Expected Annual "
        "Loss (exposure), each split at the statewide median → Priority / Monitor / Harden / Low "
        "priority. Not an external standard.",
        "source": "FireLens construction over the ingested FWI + cited FEMA NRI",
        "grain": "ZIP, static",
        "time_range": "recent era × 2025",
        "basis": "constructed",
    },
]

# Plain-language meaning of each quadrant category FOR A RESIDENT (single source for the
# decision-tool tooltips + the Methods page). Tied to the quadrant's construction below.
QUADRANT_BASIS = (
    "FireLens construction: recent-era mean Fire Weather Index (hazard) × FEMA National Risk "
    "Index expected annual loss (exposure), each split at the statewide median. Not an external standard."
)
QUADRANTS = {
    "priority": {
        "label": "Priority",
        "meaning": "Dangerous fire weather AND a lot of built value at risk — high on both axes. "
        "Managing fuels and making homes fire-resistant both matter here.",
    },
    "harden": {
        "label": "Harden",
        "meaning": "Significant property at risk while the fire weather runs below the statewide "
        "median — the stakes are about what's here, not how often it burns. Focus on making homes "
        "fire-resistant: clearing brush, ember-proofing vents.",
    },
    "monitor": {
        "label": "Monitor",
        "meaning": "Dangerous fire weather but relatively little built exposure — stay aware during "
        "fire season; fewer structures are at stake than in high-exposure areas.",
    },
    "low_priority": {
        "label": "Low priority",
        "meaning": "Below the statewide median on both fire weather and built exposure — lower "
        "relative concern, though no place is risk-free.",
    },
}
