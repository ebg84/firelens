# SCHEMA.md — metric domain contract (AUTO-GENERATED)

Do not edit by hand. Regenerate: `python prep/07_export.py`. Source of truth:
`prep/domains.py` -> `data/manifest.json` (`metric_domains`) -> this file.
**Consumers (map/analytics) MUST read the manifest contract, never hardcode grain.**

| metric | state | spatial_grain (+join path) | join_key | temporal_range | granularity | vintage |
|---|---|---|---|---|---|---|
| `fwi` | served | cell(824)->ZIP via zip_cell_map | `cell_id|zip` | 1940-2026 | era-trend|annual|weekly-pctile | GEFF-ERA5 v4.1 |
| `season_length` | served | cell(824)->ZIP via zip_cell_map | `cell_id|zip` | 1940-2026 | era-trend|annual | GEFF-ERA5 v4.1 |
| `dc_pctile` | served | cell(824)->ZIP via zip_cell_map | `cell_id|zip` | 1940-2026 | era-trend|weekly-pctile | GEFF-ERA5 v4.1 |
| `fire_events` | served | point->cell(556) | `cell_id|fire_id` | 1992-2025 | point-events | FPA-FOD 6th ed (92-20) + FRAP 25_1 (21+) |
| `vpd` | pending | cell->ZIP via zip_cell_map (when landed) | `cell_id|zip` | 1980-2026 | daily->annual | ERA5 (CDS daily-statistics) |
| `cdd` | pending | cell->ZIP via zip_cell_map (when landed) | `cell_id|zip` | 1980-2026 | daily->annual | ERA5 (CDS daily-statistics) |
| `dry_wind_days` | pending | cell->ZIP via zip_cell_map (when landed) | `cell_id|zip` | 1980-2026 | daily->annual | ERA5 (wind, pending) |
| `nri` | additive | ZIP(1693) | `zip` | 2025-snapshot | static | FEMA NRI v1.20 (Dec 2025) |
| `priority_matrix` | additive | ZIP(1693) | `zip` | static | static | FWI-era x NRI-2025 |
| `firms_density` | pending | hex/cell | `hex_id|cell_id` | 2000-present | all-time-density | NASA FIRMS (MODIS+VIIRS) |
| `fuel_context` | pending | ZIP/cell | `zip|cell_id` | current-cycle | static | LANDFIRE FBFM40 |
