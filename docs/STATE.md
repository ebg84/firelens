# STATE.md — resume-point handoff

The repo holds the code/tests/manifest. **This doc holds the JUDGMENT a fresh context
can't reconstruct.** Sections 2/3/6 are the durable, irreplaceable part; Section 1 is a
live snapshot — **re-verify it against `git log`, `git status`, and the harvest count on
resume.**

---

## 1. STATUS — live snapshot (as of 2026-06-12 22:02 PDT; RE-VERIFY ON RESUME)
- **Last commit:** `65e7e8a` (2026-06-12 22:00 −0700) — "validation sweep (validated baseline)".
- **Committed (the validated baseline):** M1 ingest → M2 geography → M3 registry → M5a
  aggregates → M6 pairing → **M7 gated export (spine-now foundation, `2ab030c`)** → 8a/8b
  NRI+matrix (`b2eede2`) → coherence framework (`58f4f59`) → 8c fuel (`c7a045e`) →
  validation sweep (`65e7e8a`).
- **Uncommitted (11 files, HELD = Lane A, pending the harvest):** `prep/04b_fetch_era5_daily.py`,
  `prep/04c_ingest_dailies.py`, `prep/ingest_dailies.py`, `prep/04_fetch_dailies.py`(M),
  `prep/fields.py`(M, K→°C/m→mm), `prep/morning_runbook.sh`, `tests/prep/test_dailies.py`,
  `tests/prep/test_ingest_dailies.py`, `tests/prep/test_tracer.py`(M, idempotency),
  `restart_processes.md`, `docs/EXPORT_GATE_REPORT.md`.
- **Tests:** **91 passed / 7 pending-by-design** — the 7 are ALL `test_dailies` (schema,
  cells_match, temperature_range, dewpoint, precip_nonneg, year_coverage, date_span) —
  red ONLY because the dailies harvest hasn't landed. Everything else green.
- **Harvest:** **9 / 141** ERA5 daily NetCDFs in `raw/era5_daily/` (Phase-1 t_max only).
- **Running in background:** `prep/04b_fetch_era5_daily.py` (pid 35684, caffeinate-wrapped)
  — the developer's CDS harvest, in the developer's terminal. Resumable (skip-existing).
- **`data/` baseline drift = CLEAN; Tubbs anchor = 0.9618.**

---

## 2. DECISIONS LOCKED — with reasoning (THE IRREPLACEABLE PART)

**NRI is a CONTRAST/DECOMPOSITION layer, NOT a validation.** FWI measures *hazard* (how
dangerous the weather); NRI measures *consequence* (Risk = Expected Annual Loss ×
SocialVulnerability ÷ Resilience — exposure-dominated). They are **orthogonal axes**. The
near-zero correlation (Spearman +0.10 vs WFIR_AFREQ, −0.04 vs WFIR_RISKS, **−0.009 vs raw
building exposure**) is **EXPECTED and is the finding** — a strong correlation would mean
the layers are redundant. **NEVER spin the correlation as a win.** Exhibit: Death Valley
(FWI 40.9, the most extreme weather; EALT $2,714 — nobody there) vs Pacific Palisades
(FWI 28.9; EALT $6.8M — WUI exposure). One-liner: *Fire Factor is the credit score;
FireLens is the credit report.*

**Hazard×exposure matrix = the product feature (8b).** Per-ZIP quadrants from FWI hazard ×
NRI EALT exposure, split at statewide medians: priority/monitor/harden/low_priority
(438/408/408/439). The **priority quadrant (high BOTH) is an output neither layer produces
alone** — FWI is blind to who's there, NRI's composite hides the hazard. *"FEMA gives the
score; FireLens gives the two axes underneath — so you know whether to manage the fuel or
harden the homes."*

**Mean-vs-tail limitation — PENDING FIX (build-day).** The matrix's hazard axis is recent-era
**MEAN** FWI, which **buries the tail**: Santa Rosa (the Tubbs city) lands in `harden`
(mean 19.4 < median 22.3) even though Tubbs ignited on a **97th-percentile** day. FIX:
switch the hazard axis to **high-percentile-day count** (or `dry_wind_days`) — it re-sorts
Santa Rosa into `priority` AND unifies with the **Tubbs 0.962** headline (both tail-based).
Deferred as a metric-axis decision, not done tonight.

**`dry_wind_days` — KEEP PENDING ON WIND, do NOT redefine.** Never ship a "dry_wind_days"
with no wind in it. CDS daily-statistics cannot produce wind-speed-max (gust param is
do-not-use; can't make speed-max from components). `vpd` already carries the honest dryness
signal for the demo. Wind arrives via the **GEE ERA5 u/v backfill** (build-day) — u/v wind
components give a computable speed-max.

**Fuel (8c) = the SUBSTRATE axis ("what's here to burn").** Understandable layer (fuel type
per ZIP from LANDFIRE FBFM40), but **NOT a substitute for weather conditions** — its own
lane. Burnable composition is meaningful **only where `burnable_frac` is substantial**
(363 ZIPs <10% burnable = urban) → show `burnable_frac` primary, composition secondary; a
99%-urban ZIP must never read "timber." Validation: Palisades reads shrub/chaparral
(SH=0.66) — matches the Jan-2025 fire. 30 m native grain → a continuous depth layer.

**Manifest-domains coherence contract.** Consumers (map/analytics) **READ `metric_domains`**
(spatial_grain + join path, temporal_range, granularity, vintage, state) and refuse/omit
out-of-domain requests — **never hardcode grain/range/granularity.** `prep/domains.py` is the
source; `docs/SCHEMA.md` is generated from it; `docs/CONSUMER_BINDING.md` is the build-day
binding rule + the 8-item fragility list. A pending→served promotion auto-enables consumers
with zero code change.

---

## 3. PROVENANCE BOUNDARY (state explicitly — the integrity story for judges)
- **Data layer (everything in this repo so far)** = built tonight / pre-event, **disclosed
  as prior work** (README Provenance; ARCHITECTURE Ledger L7). The whole prep pipeline,
  serving layer, NRI/fuel/matrix, and the coherence/validation frameworks.
- **`app/` (API, agent, report, map, deploy)** = **event-built ONLY** (Friday). Nothing under
  `app/` exists yet, by design.
- **Git timestamps must corroborate.** All data-layer commits are dated pre-event;
  **never squash, never backdate.** The commit history IS the receipt that the platform was
  built during the event and the data was prior work.

---

## 4. PENDING / DEFERRED — with why (so they're not mistaken for forgotten)
- **ERA5 harvest crawling** (9/141, ~40 min/file, CDS queue jammed, days out). `vpd`/`cdd`
  are **served-when-landed**, **decoupled from the deliverable by design** — Module 7 ships
  without them; they fold in via idempotent re-export. Not a blocker.
- **Wind NOT coming for v1 via CDS** (daily-stats can't make speed-max). Documented
  limitation; `dry_wind_days` pending.
- **GEE ERA5 backfill = the build-day raw-data task.** `ECMWF/ERA5/DAILY` +
  `ECMWF/ERA5_LAND/DAILY_AGGR` on Google Earth Engine give raw temp/precip/wind, **bypass the
  CDS queue**, and **u/v components → computable wind speed** (unblocks vpd/cdd/dry_wind_days
  AND raw measurements). This is the path, not the stalled CDS harvest.
- **FIRMS / LANDFIRE-WHP deferred** (additive; fold in via re-export). FIRMS not staged;
  fuel (FBFM40) IS done (8c); WHP is a separate later layer.
- **Raw single-variable measurements: NONE queryable today** — the spine is GEFF *indices*
  (fwi/erc/dc) only; the ERA5 inputs were never downloaded. The demo foregrounds
  indices + fuel + exposure; raw weather is honestly **"landing"** (harvest / GEE).

---

## 5. NEXT ACTIONS — in order, with gating logic (each sits on the prior's committed ground)
- **(a) DONE** — accept + document the 92 orphan cells (full-CA-coverage framing; not trimmed).
- **(b) DONE** — commit the validated stack (8c + validation + framework + 8a/8b) as honest
  timestamped commits. **This was the durable lock (`65e7e8a`).**
- **(c) NEXT — meta-validation / mutation testing.** Prove the gates have TEETH (Layer-1
  objective): inject a mutation (e.g. break a join key, shift a date, swap a CRS) and confirm
  the matching gate goes RED. Spot-verify at least one mutation yourself.
- **(d) DuckDB as a GENERATED artifact** from the served layer — gitignore the `.duckdb`,
  commit the *builder*, diff-validate the built DB vs the source parquets (never a 2nd source
  of truth).
- **(e) GitHub push** — `.gitignore` raw/ + `*.nc` + `*.duckdb`; provenance README; **the
  developer authenticates and pushes (the agent cannot).**

---

## 6. TRAPS ALREADY HIT (do not re-hit)
- **Denominator bug:** intensive metrics (NRI risk/freq) = weighted-average WITH the explicit
  `Σ(v×w)/Σ(w)` denominator; extensive (EAL $) = bare allocation `Σ(v×w)`. Bare-sum on an
  intensive field mis-scales every ZIP.
- **Fitted-threshold workaround:** gates assert the **ROOT CAUSE**, not a tuned number (NRI
  coverage gate asserts *0 recoverable* gaps — 104 non-residential + 4 F8 — not a fitted 93%).
- **CRS mismatch (#1 zonal-stats bug):** the fuel raster is a **custom CA-Albers** (center
  38°/−119.25°), **NOT EPSG:5070** — reproject the ZCTAs to the *raster's own* CRS, verify.
- **LFPS / FBFM40:** filename prefix `LF20XX_FBFM40`; read the code→class map from the shipped
  `.vat.dbf` (FBFM40 prefix groups), never hardcode the codes.
- **HUD crosswalk:** direction is **TRACT→ZIP** (RES_RATIO sums to ~1 per TRACT, so normalize
  per-ZIP for intensive averages); vintage **2025Q4** matches NRI's 2020-tract geographies.
- **Longitude convention:** GEFF NetCDFs are 0–360 (→ `to_signed_lon`); CDS ERA5 daily is
  ALREADY signed (idempotent). **FWI is open-ended** (corpus max ~238, NOT [0,150]).
- **Probe-file skip:** the `daily_mean` probe in `raw/era5_daily/` must be auto-skipped by the
  melt (not a serving combo) or it crashes the ingest.

---

## 7. OVERNIGHT LOOP
Harvest audit + read-only integration-integrity audit (`prep/audit_integrity.py`), **hourly,
READ-ONLY, HALTING at every decision** — no mutation, promotion, commit, or judgment-call
refinement autonomously. **Re-arm the hourly ScheduleWakeup on resume.**

---

> **If you read nothing else:** the validated baseline is committed (`65e7e8a`, drift CLEAN,
> Tubbs 0.9618). **The single next action is (5c) meta-validation / mutation testing — prove
> the gates have teeth before building further.** Everything additive folds in via idempotent
> re-export; the harvest is decoupled; never spin the NRI null as a win.
