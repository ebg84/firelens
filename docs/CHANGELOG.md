# CHANGELOG.md — the build arc (commit by commit, from git)

Chronological, from `git log` (all 2026-06-12, the pre-event data-layer build day). The
~7-hour gap between M6 (14:03) and M7 (21:12) is where the dailies/Lane-A/NRI exploration
happened before the export was locked.

| commit | time | what |
|---|---|---|
| `856e4e7` | 10:10 | **Docs & contracts** — the brief, locked architecture, RUBRIC (prior work, disclosed). |
| `291abfc` | 11:52 | **M1 — GEFF ingest → weather spine.** 29 blocks → `geff_spine` (64.6M rows, 1940–2026); F1 cell_id from file coords; FWI documented open-ended. |
| `86c61c5` | 12:31 | **M2 — geography J1–J3.** cell_meta (824 in-CA), zip_meta (1801 ZCTAs), zip_cell_map (area-weighted, sums to 1.0), county/land_frac. |
| `be47de4` | 13:05 | **M3 — Metric Extension Protocol.** Registry (`prep/metrics.py`) + v1 formulas (Magnus/VPD, red-flag, CDD, season); Open-Meteo probe. |
| `261855b` | 13:57 | **M5a — registry-driven aggregation (spine half).** annual_metrics, pctile_lut, zip_trends for fwi/season_length (+dc/erc candidates); dummy-propagation proof. |
| `733a8ca` | 14:03 | **M6 — occurrence ingest + FWI pairing.** FPA-FOD (251,881 CA) + FRAP (23,334), F2 era split, fire_events (3,205); **Tubbs anchor 0.962**. |
| `2ab030c` | 21:12 | **M7 — gated serving-layer export (the locked spine-now foundation).** data/ (7 tables, 5.6 MB) + manifest; dc_pctile promoted to v1; gate refuses on red. |
| `b2eede2` | 21:27 | **8a/8b — NRI consequence + hazard×exposure matrix.** NRI→ZIP (residential-weighted), correlation (+0.10/−0.04 = orthogonal, the decomposition); quadrants. |
| `58f4f59` | 21:39 | **Coherence framework — metric_domains contract.** manifest domains + generated SCHEMA.md; per-metric enforcement gates; CONSUMER_BINDING + integrity audit. |
| `c7a045e` | 22:00 | **8c — LANDFIRE FBFM40 fuel.** raster zonal (custom CA-Albers CRS), code→class from .vat, non-burnable masked; coverage 1801/1801; Palisades reads chaparral. |
| `65e7e8a` | 22:00 | **Validation sweep — join-resolution (validated baseline).** 7/7 checks; orphan-cell finding accepted; re-runnable gates. |
| `1c2ff49` | 22:05 | **STATE.md** — resume-point handoff (the judgment a fresh context can't reconstruct). |
| `b29daf1` | 22:15 | **Authoritative reference docs** — VARIABLES/MAPPINGS/ANALYTICS/CHANGELOG generated from ground truth; ARCHITECTURE Part 3 decision record (D1–D7); first DDL-drift flags. |
| `35690db` | 22:31 | **Meta-validation** — `prep/meta_validate.py` mutation-tests the suite (10 gates proven to have TEETH, negative control green); `META_VALIDATION.md`; surfaces the null-fabrication gap + `structures_destroyed` finding. |
| `2962b43` | 22:47 | **Additive promotion** — `nri_zip`/`zip_priority_matrix`/`fuel_context` promoted into committed `data/` (HEAD-reproducible); manifest.tables registered; fuel composition NULL'd for zero-burnable. |
| `3743a4e` | 23:00 | **Fuel NULL fix + blind-spot closure** — 34 (not 12) NULL-composition ZIPs (22 no-raster + 12 nothing-burnable); strengthened `check_metric_spatial_universe` to assert the fuel coverage decomposition the sweep had missed. |
| `66491c8` | 23:02 | **DuckDB serving DB** — `prep/build_duckdb.py` (generated, read-only, from committed `data/`); `cell_annual` + `zip_serving` views + `metric_domains` table; diff-validation gate (suite 98 pass / 7 dailies-pending). |
| `68253a9` | 23:03 | **Pending-decision log** — fuel `dominant_class` no-raster mislabel recorded (c-e); claim-without-data ledger. |

**Held uncommitted (Lane A, pending harvest):** `04b_fetch_era5_daily`, `04c_ingest_dailies`,
`ingest_dailies`, the K→°C conversions, `test_dailies` — fold in via re-export when the ERA5
dailies land (harvest or build-day GEE).

**Module numbering note:** geography committed as `03`; the sequence is 01,03,04,05,06,07
(no `02`) — intentional, the filenames narrate the actual build order.
