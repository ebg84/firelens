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

## ADDITIVE (interim, joined; NRI never a served risk column)
| variable | table | definition | units / range | source |
|---|---|---|---|---|
| `wfir_risks` | nri_zip (1693) | FEMA wildfire composite Risk Index (EAL × SoVI ÷ Resilience) | 0–100 | FEMA NRI v1.20 |
| `wfir_afreq` | nri_zip | annualized wildfire frequency (the hazard analog) | 0–~0.065 /yr | FEMA NRI |
| `wfir_ealt` | nri_zip | expected annual loss (total $) | $ (0–$36M tract) | FEMA NRI |
| `quadrant` | zip_priority_matrix (1693) | priority / monitor / harden / low_priority (FWI hazard × NRI exposure) | categorical | 8b |
| `fwi_level` | zip_priority_matrix | recent-era mean FWI (the matrix hazard axis) | index | derived |
| `burnable_frac`,`non_burnable_frac` | fuel_context (1801) | share of pixels burnable / non-burnable | 0–1 | LANDFIRE FBFM40 LF2025 |
| `{grass,grass_shrub,shrub,timber_understory,timber_litter,slash_blowdown}_frac` | fuel_context | fuel-class composition OF BURNABLE pixels | 0–1 (sum to 1) | LANDFIRE |
| `dominant_class`, `total_px` | fuel_context | dominant fuel group; pixel count | categorical / int | LANDFIRE |

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

## DRIFT vs DATA.md §5 DDL (flagged)
- `annual_metrics` DDL declared `vpd_max_mean, red_flag_days, cdd_max` (the **pending** dailies
  columns) and **omitted** `dc_max, erc_mean` — reality has dc_max/erc_mean now, dailies pending.
- `fuel_context` DDL declared `class_json`; reality uses **explicit per-group fraction columns**
  + `non_burnable_frac` + `total_px`. The implementation is richer than the DDL.
