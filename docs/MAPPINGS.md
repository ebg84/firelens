# MAPPINGS.md — all temporal + spatial connections (generated from the actual joins)

Every join/mapping in the layer, with source→target grain, key, weighting, temporal
domain, and the conservation note (aggregated vs native). Orphan/coverage counts from
`prep/validate.py` (the join-resolution sweep). Ground truth as of `1c2ff49`.

## Spatial joins
| join | source grain → target | key | weighting | conservation | coverage / orphans (both directions) |
|---|---|---|---|---|---|
| **cell → ZIP** (`zip_cell_map`) | 0.25° cell (824 in-CA) → ZCTA (1801) | cell_id ↔ zip | **area-weighted**, weights sum 1.0/ZIP | aggregate-up (fine→coarse); coarse never disaggregated | **0 orphan ZIPs** (all 1801 served); 92 orphan cells (in-CA beyond any ZCTA — ACCEPTED slack); 732 cells actually serve a ZIP |
| **tract → ZIP** (NRI, `nri_zip`) | 2020 census tract → ZCTA (1693) | TRACTFIPS ↔ ZIP | **residential** (HUD RES_RATIO): intensive = avg WITH Σ-weight denominator, extensive ($) = bare allocation | intensive averaged, extensive conserved | 1693/1801; **108 gap = 104 non-residential + 4 F8** (accounted, not a hole) |
| **raster → ZIP** (fuel, `fuel_context`) | 30 m FBFM40 pixel → ZCTA (1801) | spatial zonal (raster CRS) | pixel-count composition, non-burnable masked | composition (fractions) | **1801/1801**; 12 zero-burnable (urban, flagged) |
| **point → cell** (`fire_events`) | ignition point → 0.25° cell (556 cells) | nearest cell centroid (≤22 km) | bounded snap | point retains lat/lon (haversine app-side) | 3,205 events; 556 distinct cells |
| **cell → county** (`cell_meta`) | cell → county FIPS | majority-area | — | inherit-down (labeled) | every in-CA cell has a county |
| **ZCTA → county** (`zip_meta`, G7) | ZCTA → majority-area county FIPS | spatial | majority area | border ZIP → one county | documented (ZCTAs cross county lines) |

**CRS note:** geography joins are EPSG:5070; the **fuel raster is a custom CA-Albers** (center
38°/−119.25°) — the ZCTA overlay is reprojected to the *raster's own* CRS (the #1 zonal bug).

## Temporal domains (per source)
| source | range | granularity | vintage |
|---|---|---|---|
| spine (fwi/erc/dc) | 1940–2026 | daily → annual / weekly-pctile | GEFF-ERA5 v4.1 |
| fire_events | 1992–2025 | point-events | FPA-FOD 6th ed + FRAP 25_1 |
| NRI / matrix | **2025 snapshot** | STATIC (no time axis) | FEMA NRI v1.20 (Dec 2025) |
| fuel | current cycle | STATIC | LANDFIRE FBFM40 LF2025 |
| vpd/cdd/dry_wind_days (pending) | 1980–2026 | daily → annual | ERA5 (CDS/GEE) |

## The matrix cross (cross-sectional, NOT temporal)
`priority_matrix` joins, per ZIP, **`fwi_level` (recent-era mean, "current") × `wfir_ealt`
(2025)** → quadrant, split at statewide medians. It is a **cross-sectional** join on `zip`
(both "current state"), carrying **no time dimension** — it never pairs a 1940 trend point
with a 2025 snapshot. (Validation check #6 confirms no stored time dim.)

## The spine
`(cell_id, date)` is the master spine: weather indices native at cell×date (64.6M rows,
1940–2026). Occurrence snaps to it (point→cell, date); fuel/NRI/regulatory are static
attributes OF the ZIP; trends aggregate the spine by year and compare eras. Every served
ZIP value is a `zip_cell_map`-weighted walk along the spine.

## Materialized in the DuckDB (`prep/build_duckdb.py`)
These joins surface as two read-only VIEWS over the committed parquet: `cell_annual`
(`annual_metrics ⋈ cell_meta` → the 824-cell field + lat/lon) and `zip_serving` (canonical
1,801 ZCTAs LEFT JOIN the pivoted `zip_trends` + `nri_zip` + `zip_priority_matrix` +
`fuel_context` → one current/snapshot row per ZIP, NULLs honest: 108 NRI-absent, 34
fuel-undefined). The wide row is a VIEW, never a second source of truth.
