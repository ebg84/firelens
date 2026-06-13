# VARIABLES.md — complete variable catalog (generated from manifest + actual parquet columns)

Ground truth as of `1c2ff49`. Grouped by state. Spine = GEFF *indices* only; raw weather
measurements are NOT present (see "Not present"). Units/range from the actual data.

## SERVED (live in `data/`, in `manifest.served_metrics`)
| variable | table(s) | definition | units / range | source |
|---|---|---|---|---|
| `fwi_mean`, `fwi_max` | annual_metrics (cell,year) | annual mean/max Fire Weather Index | open-ended index (corpus max ~238) | GEFF-ERA5 v4.1 |
| `extreme_days` | annual_metrics | days/yr FWI ≥ 38 (EFFIS "extreme") | int days | derived from spine FWI |
| `season_len` | annual_metrics | days/yr FWI ≥ 21.3 (EFFIS "high") = **season_length** | int days | derived from spine FWI |
| `dc_max` | annual_metrics | annual max Drought Code = **dc_pctile** source | open-ended index | GEFF DC |
| `fwi`,`dc_pctile` pctiles | pctile_lut (metric,cell,iso_week) | weekly p10–p99 climatology (1940–2026 pooled) | index thresholds | GEFF |
| `fwi`/`season_length`/`dc_pctile` trends | zip_trends (zip,metric) | baseline(1980–2000) vs recent(2010+), pct_change, freq_ratio, robust | ratios | derived |
| `fire_events` | fire_events (fire_id) | paired fires: fwi_pctile, erc_pctile, acres, ign_date, cause_class, structures_destroyed(null) | fwi_pctile 0–1 | FPA-FOD 92–20 + FRAP 21+ |

Note: `erc_mean` (annual_metrics) and `erc_pctile` (fire_events) carry **ERC** (US NFDRS Energy
Release Component, J/m²) — acquired and shown on event cards, but NOT a primary served trend
metric (it is not in `served_metrics`).

## ADDITIVE (committed in `data/` since `2962b43`; NRI never a served risk column)
| variable | table | definition | units / range | source |
|---|---|---|---|---|
| `wfir_risks` | nri_zip (1693) | FEMA wildfire composite Risk Index (EAL × SoVI ÷ Resilience) | 0–100 | FEMA NRI v1.20 |
| `wfir_afreq` | nri_zip | annualized wildfire frequency (the hazard analog) | 0–~0.065 /yr | FEMA NRI |
| `wfir_ealt` | nri_zip | expected annual loss (total $) | $ (0–$36M tract) | FEMA NRI |
| `quadrant` | zip_priority_matrix (1693) | priority / monitor / harden / low_priority (FWI hazard × NRI exposure) | categorical | 8b |
| `fwi_level` | zip_priority_matrix | recent-era mean FWI (the matrix hazard axis) | index | derived |
| `burnable_frac`,`non_burnable_frac` | fuel_context (1801) | share of pixels burnable / non-burnable | 0–1 | LANDFIRE FBFM40 LF2025 |
| `{grass,grass_shrub,shrub,timber_understory,timber_litter,slash_blowdown}_frac` | fuel_context | fuel-class composition OF BURNABLE pixels; **NULL** for 34 undefined ZIPs (22 no-raster + 12 nothing-burnable), distinct from a real 0 | 0–1 (sum to 1) or NULL | LANDFIRE |
| `dominant_class`, `total_px` | fuel_context | dominant fuel group; pixel count (`total_px=0` ⇒ no raster coverage) | categorical / int | LANDFIRE |

## PENDING (declared in `metric_domains`, no data yet)
| variable | blocked_on | definition | dependency |
|---|---|---|---|
| `vpd` | harvest | annual mean VPD_max (drying power) | ERA5 t_max + td_mean (CDS/GEE) |
| `cdd` | harvest | consecutive-dry-day max run | ERA5 precip (CDS/GEE) |
| `dry_wind_days` | wind | Red-Flag-condition days (wind≥11.18 m/s & RH≤25%) | ERA5 wind (GEE u/v, build-day) — NOT redefined |
| `firms_density` | acquisition | satellite detection density per hex/cell | NASA FIRMS (not staged) |

## NOT PRESENT — raw single-variable measurements
**None queryable today.** The spine is `[cell_id, date, fwi, erc, dc]` — GEFF *indices* only;
the ERA5 inputs GEFF used were never downloaded. Temperature, dewpoint/humidity,
precipitation, wind: all **landing** via the ERA5 harvest / build-day GEE backfill. The demo
foregrounds indices + fuel + exposure; raw weather is honestly "landing."

## ALL-NULL columns (claim-without-data — present in schema, 100% NULL, do NOT fabricate)
- `fire_events.structures_destroyed` (3205/3205 NULL) — CLAUDE.md wants "5,636 structures";
  source as a cited labeled constant or drop the claim. NEVER back-fill.
- `fire_events.erc_pctile` (3205/3205 NULL) — VARIABLES once said "shown on event cards";
  compute from the spine ERC LUT or drop from the event-card spec.
- `zip_trends.robust` (all NULL) — populate the robustness flag in `05_aggregates` or drop it.
  Absence ≠ "not robust". (See STATE.md §5 c-b/c-d; pinned by the DuckDB diff-gate.)

## Serving surface
The app reads a generated `firelens.duckdb` (`prep/build_duckdb.py`) over this parquet: base
tables 1:1, plus `cell_annual` (824-cell field view), `zip_serving` (1,801-canonical wide view),
and `metric_domains` (the contract). Reproducible from committed `data/` alone.

## DRIFT vs DATA.md §5 DDL — RECONCILED (`2026-06-13`)
DATA.md §5 carried an AS-BUILT RECONCILIATION callout and corrected DDLs for `annual_metrics`
(dc_max/erc_mean present; vpd/red_flag/cdd pending) and `fuel_context` (explicit group fractions
+ `non_burnable_frac` + `total_px`, not `class_json`). `county_trends`/`firms_density` remain
DECLARED-but-NOT-BUILT. This catalog is the authoritative as-built reference.
