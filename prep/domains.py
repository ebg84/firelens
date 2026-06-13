"""prep/domains.py — per-metric spatial/temporal coherence CONTRACT (source of truth).

prep/07_export.py writes this into data/manifest.json (`metric_domains`) and generates
docs/SCHEMA.md from it; tests/prep/test_domains.py verifies the ACTUAL parquets match
each metric's DECLARED grain (per-metric, never a universal 1,801 assert). spatial_grain
is the actual grain + join PATH (a description), not a single canonical number.
"""
REQUIRED = ["spatial_grain", "join_key", "temporal_range", "temporal_granularity",
            "vintage", "state"]

DOMAINS = {
    "fwi": {
        "spatial_grain": "cell(824)->ZIP via zip_cell_map",
        "join_key": "cell_id|zip",
        "temporal_range": "1940-2026",
        "temporal_granularity": "era-trend|annual|weekly-pctile",
        "vintage": "GEFF-ERA5 v4.1",
        "state": "served",
        "tables": ["annual_metrics", "pctile_lut", "zip_trends"],
    },
    "season_length": {
        "spatial_grain": "cell(824)->ZIP via zip_cell_map",
        "join_key": "cell_id|zip", "temporal_range": "1940-2026",
        "temporal_granularity": "era-trend|annual", "vintage": "GEFF-ERA5 v4.1",
        "state": "served", "tables": ["annual_metrics", "zip_trends"],
    },
    "dc_pctile": {
        "spatial_grain": "cell(824)->ZIP via zip_cell_map",
        "join_key": "cell_id|zip", "temporal_range": "1940-2026",
        "temporal_granularity": "era-trend|weekly-pctile", "vintage": "GEFF-ERA5 v4.1",
        "state": "served", "tables": ["pctile_lut", "annual_metrics", "zip_trends"],
    },
    "fire_events": {
        "spatial_grain": "point->cell(556)", "join_key": "cell_id|fire_id",
        "temporal_range": "1992-2025", "temporal_granularity": "point-events",
        "vintage": "FPA-FOD 6th ed (92-20) + FRAP 25_1 (21+)",
        "state": "served", "tables": ["fire_events"],
    },
    "vpd": {
        "spatial_grain": "cell->ZIP via zip_cell_map (when landed)", "join_key": "cell_id|zip",
        "temporal_range": "1980-2026", "temporal_granularity": "daily->annual",
        "vintage": "ERA5 (CDS daily-statistics)", "state": "pending",
        "blocked_on": "harvest", "lane": "Lane A CDS (t_max+td_mean) -> 05 rerun", "tables": [],
    },
    "cdd": {
        "spatial_grain": "cell->ZIP via zip_cell_map (when landed)", "join_key": "cell_id|zip",
        "temporal_range": "1980-2026", "temporal_granularity": "daily->annual",
        "vintage": "ERA5 (CDS daily-statistics)", "state": "pending",
        "blocked_on": "harvest", "lane": "Lane A CDS (precip) -> 05 rerun", "tables": [],
    },
    "dry_wind_days": {
        "spatial_grain": "cell->ZIP via zip_cell_map (when landed)", "join_key": "cell_id|zip",
        "temporal_range": "1980-2026", "temporal_granularity": "daily->annual",
        "vintage": "ERA5 (wind, pending)", "state": "pending",
        "blocked_on": "wind", "lane": "wind ladder (CDS daily-stats wind upstream issue)", "tables": [],
    },
    "nri": {
        "spatial_grain": "ZIP(1693)", "join_key": "zip",
        "temporal_range": "2025-snapshot", "temporal_granularity": "static",
        "vintage": "FEMA NRI v1.20 (Dec 2025)", "state": "additive",
        "note": "1693 != 1801: 104 non-residential + 4 F8 (consumer omits-with-note)",
        "tables": ["nri_zip (interim)"],
    },
    "priority_matrix": {
        "spatial_grain": "ZIP(1693)", "join_key": "zip",
        "temporal_range": "static", "temporal_granularity": "static",
        "vintage": "FWI-era x NRI-2025", "state": "additive",
        "tables": ["zip_priority_matrix (interim)"],
    },
    "firms_density": {
        "spatial_grain": "hex/cell", "join_key": "hex_id|cell_id",
        "temporal_range": "2000-present", "temporal_granularity": "all-time-density",
        "vintage": "NASA FIRMS (MODIS+VIIRS)", "state": "pending",
        "blocked_on": "acquisition", "lane": "raw/firms/ not staged", "tables": [],
    },
    "fuel_context": {
        "spatial_grain": "ZIP/cell", "join_key": "zip|cell_id",
        "temporal_range": "current-cycle", "temporal_granularity": "static",
        "vintage": "LANDFIRE FBFM40", "state": "pending",
        "blocked_on": "acquisition", "lane": "raw/landfire/ not staged", "tables": [],
    },
}
