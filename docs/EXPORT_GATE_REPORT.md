# Module 7 — Export Gate Report (2026-06-12, SPINE-NOW)

Written to disk per the pre-departure checkpoint. The export is **built, gated, and
green**; the commit is **stacked for approval** (not committed).

## Gate status — `tests/prep/` (60 passed, 7 pending-by-design)
| Suite | Result | Gates |
|---|---|---|
| test_tracer | 10 ✅ | F1 round-trip, gapless 1940–2026, fault-injection, signed-lon idempotency |
| test_geography | 5 ✅ | J1–J3, weights=1.0, land_frac, 5 ref-ZIP counties, no orphans |
| test_metrics | 14 ✅ | Tier-2 formulas, registry contract, dummy-propagation, dc_pctile promoted |
| test_aggregates | 6 ✅ | LUT monotonic, annual sanity, served trends (fwi/season_length/dc_pctile) |
| test_fpa_fod / test_fire_events / test_pairing | 15 ✅ | completeness, F2 split, **Tubbs anchor 0.962** |
| test_ingest_dailies | 3 ✅ | real-probe melt (K→°C, F1), merge, units-assert |
| **test_export** | **7 ✅** | manifest contract (F6), ≤100 MB, in-CA filter, served metrics, Tubbs survives |
| test_dailies | 7 ⛔ | pending the harvest (t_max/td_mean/precip) — correct |

## Export contents (`data/`, 5.60 MB — well under the 100 MB budget)
| Table | Rows |
|---|---|
| cell_meta | 824 (in-CA) |
| zip_meta | 1,801 |
| zip_cell_map | 4,415 |
| annual_metrics | 71,688 (in-CA only — AUDIT [Med] closed) |
| pctile_lut | 85,696 (fwi + dc_pctile) |
| zip_trends | 5,403 (fwi, season_length, dc_pctile) |
| fire_events | 3,205 (Tubbs fwi_pctile = 0.962) |
| manifest.json | served_metrics=[dc_pctile, fwi, season_length]; pending={vpd, cdd, dry_wind_days} w/ lanes |

## RUBRIC R1 mapping
- ✅ Anchor: Tubbs 2017 ≥ 0.90 (**0.962**) survives the export.
- ✅ `data/manifest.json` exists; `data/` = 5.60 MB ≤ 100 MB.
- ✅ F2 era-dedup: 0 violations (test_pairing).
- ✅ Gate refuses on red (verified — it caught the dc_pctile cascade mid-build).
- ⏸ `pytest -m "tier1 or tier2"` full green pends the dailies harvest (test_dailies).

## Pending (fold in via the morning runbook after the harvest)
- `vpd`, `cdd` — Lane A CDS harvest → `05_aggregates` rerun → re-export (zero code change).
- `dry_wind_days` — wind ladder (CDS daily-stats wind upstream issue; forum tripwire in DATA.md).
- Precip accumulation-day convention — auto-checked at first `total_precipitation` melt.
