# AUDIT.md — FireLens continuous self-audit

Data-layer doc; a running receipt of the standing self-audit (code + process).
Committed with Module 7. Severity: **Blocking** (stops tonight's export) ·
**High** · **Medium** · **Low**. No finding is fixed without a line here.

Sweep 1 — 2026-06-12 (after Modules 1/2/3/5a/6 + the dailies redesigns).

## Findings-Blocking (STOP, uncommitted, stacked for the developer's return)
- **[Resolved 2026-06-12] Probe staged → real-proof GREEN.** The 9bad5726 output
  (`2m_temperature_daily_mean_2025.nc`) is now in `raw/era5_daily/`. Verified against
  the developer's independent first contact: var `t2m`, units `K`, `valid_time` 365
  gapless / 0 NaN, grid 57×47 / 45→31 / −125→−113.5 signed, scalar `number` dropped,
  sanity 286.73 K (01-07) / 292.61 K (07-15) at Sonoma. `test_ingest_dailies` runs
  the melt on the REAL file (K→°C, F1) — green. Synthetic remains only for the
  3-column merge.
- **[Blocking — still open] Precip accumulation-day convention.** The ERA5
  `daily_sum` day-attribution (a wrong call shifts every CDD by one day) cannot be
  settled until a `total_precipitation` file lands — only a `2m_temperature` probe
  exists. Named, pending the tp harvest. (Developer noted: correct.)
- The spine-export path (fwi/season_length trends, fire_events incl. the Tubbs 0.962
  anchor, geography) is otherwise clean.

## Findings-Fixed (in place this sweep; one-line rationale)
- **[Med]** `tests/prep/test_dailies.py` required `t_min`, which the redesigned
  essential-4 fetch deliberately does not produce (no v1 metric consumes t_min).
  Removed it from the schema assertion; range check now uses `td_mean`/`t_max`.
  Class (a) drift + (c) gate-tests-wrong-column. (Uncommitted red test, pre-green.)
- **[Med]** Quarantined 4 stale dailies checkpoints (7-var, **pre-doctrine, no
  verified `models=era5`** → grid-betrayal/IFS-splice risk) to
  `$FIRELENS_DATA/interim/quarantine/dailies_pre_doctrine/`. The clean governed
  fetch must not inherit unverified-grid data. Class (a)/(d) seam. Reversible.
- **[Low]** `docs/DATA.md` §7 "metric enum" → "served metric set" — stale
  enum→registry wording left by the restructure. Class (b) remnant.

## Findings-Deferred (real, post-event)
- **[High]** **CDS-pivot Kelvin trap.** If dailies come from CDS/raw ERA5 (the
  recommended Lane-B pivot), temperatures are **Kelvin**; the Magnus/VPD and
  Red-Flag formulas in `prep/metrics.py` expect **°C**. Open-Meteo returned °C so
  there is no current bug — but the CDS ingest MUST convert (−273.15) and a unit
  guard must gate it. Cost: 1 line + 1 test. Class (d) cross-source units.
- **[Med]** **Export must restrict to served cells.** `annual_metrics` and
  `pctile_lut` cover all 2,051 spine cells incl. out-of-CA NV/UT/OR padding;
  Module 7 must filter to in-CA / ZIP-served cells or it ships non-CA rows and
  bloats `data/`. Cost: a `WHERE cell_id IN (zip_cell_map)` at export. Class (d).
- **[Med]** **Pairing gate vacuous-on-empty.** `test_pairing` F2/no-dup/pctile
  asserts pass if `fire_events` were empty; only the Tubbs/Palisades rows catch
  emptiness. Add a count-band (~2,000–4,000) assertion in a named test turn.
  Class (c) empty-set trap.
- **[Low]** **`metrics.iso_week` unused in production.** Production percentiles use
  DuckDB `week()` (aggregates + pairing); the pandas `iso_week` exists only for a
  formula test and Friday's live path. Two impls can diverge. Consolidate or
  document DuckDB `week()` as the production convention. Class (b)/(d).
- **[Low]** **F9 null-budget untested.** `06_pairing` filters null FRAP
  `alarm_date` but no gate asserts the input null rate <5% (the F9 contract). Add
  one assertion. Class (c).
- **[Low]** **prep/ numbering gap (no `02_*`).** Cosmetic; intentional per the
  renumber decision (01 ingest, 03 geography committed; 04→07 new). Leave or
  rename later. Class (b).
- **[Low]** **fwi_pctile self-inclusion.** The pairing percentile population
  includes the fire's own ignition day (~1 of 85 in-cell-week rows). Negligible
  upward bias; document. Class (a).

## Process-Audit (my session vs the working rules)
- **Tests-first:** held for M1/M2/M3/M5a/M6 — red shown before implementation each
  time. **Exception:** the `Governor` class (`04_fetch_dailies.py`) has no unit
  test; its charge/sleep-to-next-hour logic is unverified. Cost: a small test
  (Deferred, [Low]).
- **Approvals:** M1/M3/M5a/M6 commits had explicit "commit" approval. M2's commit I
  framed as pre-restructure cleanup, and M6 I committed on "each commit green"
  taken as standing authorization — both slightly ahead of an explicit per-commit
  yes. No objection was raised; flagged for honesty.
- **Memory:** `firelens-pipeline-state` updated this sweep to the calibration
  verdict (per-cell Open-Meteo infeasible). Other memory files current.
- **Standing instructions:** triage (data-first, metric questions deferred), scope
  guard (zero `app/` code written), read-only-scans, and raw-immutability all held
  after the early-session corrections. Write-lock respected (the FWI bound change
  was a named/approved turn; today's test_dailies edit is on an uncommitted red
  test, pre-green).

## Sweep 2 — Lane A (CDS ERA5 dailies), 2026-06-12
- **Resolved (was Deferred [High], Kelvin trap):** `fields.kelvin_to_celsius` /
  `metres_to_mm` added; `ingest_dailies.melt_file` **asserts** each file's reported
  units before converting (raises on mismatch — proven by a fault-injection test).
  No assumption; the real run is a true rerun.
- **Resolved (was Fixed, drift):** every wind/`t_min`/`t_mean`/`gust` expectation
  removed from `test_dailies` (now exactly {cell_id, date, t_max, td_mean, precip});
  wind is the documented post-event ladder, not v1.
- **New artifacts audited as written (continuity rule):** `04b_fetch_era5_daily.py`
  (manifest validated = exactly 141; frozen fields identical across years; 2026
  Jan–May guard) · `ingest_dailies.py` + `04c` (units-asserting, F1 filter,
  synthetic mechanics green) · `test_ingest_dailies.py`.
- **[Low] discrepancy logged:** the commission cited 6 legacy Open-Meteo
  checkpoints; only **4** exist on disk (all 7-col, pre-doctrine), now in
  `interim/dailies_legacy/` as the cross-source validation set.
- **[Low] filename convention:** 04b writes `<variable>_<statistic>_<year>.nc`
  (underscored, per spec); the ingest is filename-driven for (var, stat) mapping —
  if 04b's names ever change, `ingest_dailies.parse_name` must change with them.

## Sweep 3 — harvest-day module sync, 2026-06-12 (during hourly audit)
- **[Fixed, Med] Probe file would crash the production melt.** The test-article
  `2m_temperature_daily_mean_2025.nc` lives in `raw/era5_daily/`, which `04c` globs.
  `daily_mean` is not a serving combo, so `parse_name` raised — aborting the whole
  melt the moment the morning runbook ran. Fix: `parse_name` raises `UnmappableFile`
  (a ValueError subclass); `build_dailies` **skips-and-warns** on it (deliberate
  non-serving skip) while a units mismatch still hard-raises (assert-don't-assume
  preserved). Verified on the live partial harvest: probe skipped, 6 `daily_maximum`
  files → 4.06M `t_max` rows. Class (d) cross-module seam.

## Continuity rule (active)
Every new artifact (Module 7 export, the Lane-A/B scripts, doc sweeps) is audited
as written against the four failure classes — predict-then-verify on fresh code,
not just legacy. New findings append to a dated sweep below.

> Note: "Lane A" is referenced in the queue but undefined in-session; treated as
> the spine-export (Module 7) until specified.
