# DEVELOPMENT_PLAN.md — the forward plan

The structure that holds even as analytics and UI get workshopped. Read with
`docs/STATE.md` (resume-point), `docs/ARCHITECTURE.md` (the Decision Ledger), and
`docs/CONSUMER_BINDING.md` (the consumer rules). The split that governs everything below:
**the data contract, the grains, and the validation discipline are FIXED; analytics
combinations and UI/UX are FLEXIBLE.** A developer can change the flexible freely and must
not break the fixed.

---

## PART 1 — THE FIXED CORE (do not break)

### 1.1 The data-layer contract
The serving layer is `data/` (11 parquet, 5.6 MB) + `data/manifest.json` (the
pipeline↔app contract). The app validates the manifest at load and fails loudly on
mismatch. Nothing downstream may assume a schema the manifest doesn't declare.

- **Served metric set (v1, frozen):** `fwi`, `season_length`, `dc_pctile` (per-ZIP era
  trends) + `fire_events` (ignition-day percentiles). New metrics enter ONLY through the
  Metric Extension Protocol (`prep/metrics.py`: one formula fn + one registry entry;
  LUT/trend/export iterate the registry generically). The never-list — forecasts, fire
  behavior/spread, parcel, composite/invented indices — is a hard boundary.
- **Additive layers (committed, not "served risk"):** `nri_zip`, `zip_priority_matrix`
  (FEMA NRI consequence + hazard×exposure matrix), `fuel_context` (LANDFIRE). NRI is a
  *contrast/decomposition*, never spun as validating the trend; the matrix is a
  categorical quadrant, never a blended risk score.
- **Pending (declared in the manifest, fold in by re-export):** `vpd`, `cdd`,
  `dry_wind_days`, `firms_density`. A `pending→served` promotion is a DATA change, not a
  code change — consumers auto-enable from the contract.

### 1.2 The grains (fixed — every claim renders at its true grain)
| layer | native grain | serve grain | rule |
|---|---|---|---|
| weather (fwi/season_length/dc_pctile) | 0.25° cell (824) | ZIP via `zip_cell_map` (area-weighted) | aggregate fine→coarse; NEVER disaggregate below cell |
| annual series | cell × year | cell-grained `annual_metrics` | the continuous 1940–2026 line lives here, NOT in `zip_trends` |
| era trend | — | `zip_trends` = two eras + Δ | two points, never a continuous line |
| fire events | ignition point → cell (556) | points/perimeters | pairing is to cells, never a ZIP count |
| NRI / matrix | 2020 tract → ZIP (1,693) | ZIP, 2025 static | cross-sectional, no time axis |
| fuel | 30 m FBFM40 pixel | ZIP (1,801) composition | `burnable_frac` primary; composition only where burnable is substantial |

**No false precision (auditability thesis):** render only the real grains we computed
(cells, fire points). NEVER interpolate below 0.25°; NEVER imply parcel detail. "31 km
atmospheric resolution" governs every render.

### 1.3 The DuckDB serving surface (the app's read interface)
`prep/build_duckdb.py` builds a **read-only, generated** `firelens.duckdb` from committed
`data/` ONLY (binary gitignored; builder committed; rebuilt, never hand-edited). Objects:
- 10 base tables (1:1 from parquet, dtypes + true NULLs preserved).
- `cell_annual` VIEW — the 824-cell annual field + lat/lon (the non-blocky cell-field UX).
- `zip_serving` VIEW — one row per **canonical 1,801** ZCTA: era-comparison columns +
  2025-static NRI/matrix + static fuel. A CURRENT/SNAPSHOT row — **NOT a time series**.
- `metric_domains` TABLE — the coherence contract carried INTO the DB (grain/range/state
  per metric), so a consumer reads grain from the DB, never hardcodes it.

### 1.4 The coherence rules consumers MUST obey (`docs/CONSUMER_BINDING.md`)
Every map/analytics surface reads `metric_domains` per metric and refuses/omits
out-of-domain requests. The eight fragility bindings (snapshot-on-time-axis, era-as-line,
implied-daily, metric-shown-for-absent-ZIP, cell↔ZIP-direct, NRI×FWI-as-temporal,
points-as-ZIP-density, undeclared-pending-breaks-UI) are the spec. **NULL semantics are
load-bearing:** NRI-absent (108) and fuel-undefined (34) are NULL, distinguishable from a
real 0 — a consumer must render "—"/omit, never zero-fill.

### 1.5 The provenance boundary (do not blur)
Data layer = built pre-event (2026-06-12), disclosed prior work. App = built at the event
(2026-06-13). The commit history is the boundary; timestamps corroborate it. **Never
squash, backdate, or retro-edit pre-event commits.** Pre-event work that still needs doing
(e.g. the GEE backfill) is staged as a documented DATA task, not smuggled into app commits.

### 1.6 The validation gates that must stay GREEN
- `pytest -q` → **98 pass / 7 dailies-pending** (the 7 are RED-by-design until the harvest).
- Join-resolution sweep (`prep/validate.py`) → 7/7, incl. the fuel coverage decomposition
  (1767+22+12) and the composition-NULL partition invariant.
- DuckDB diff-gate (`tests/prep/test_duckdb_build.py`) → DB ≡ source on rowcount/dtype/
  NULL-count/range/ZIP-format; pins the all-NULL set.
- The **Tubbs anchor** (`fwi_pctile ≥ 0.90`, actual 0.962) survives every export.
- Meta-validation (`prep/meta_validate.py`) → 10 gates proven to have teeth.
A change that reds any of these is wrong until it's green again. Don't weaken a gate to pass.

---

## PART 2 — THE BUILD-DAY SEQUENCE (event window, 2026-06-13)

Order chosen so the primary deliverable (analyst + report) is never at risk; the map is
always cuttable, the agent never is. Pre-approved scope reductions, in order: (1) drop
FIRMS/FHSZ/fuel overlays, (2) drop the map, (3) reduce chat to two tools with cached
responses for the five reference ZIPs.

1. **App skeleton over the contract.** FastAPI service; load `data/` (or build/attach
   `firelens.duckdb`); validate `manifest.json` at startup (fail loud on mismatch). Health
   + `/api/trends/{zip}` returning real `zip_trends` JSON is the first green.
2. **The five public endpoints = the five agent tools.** `/api/trends/{zip}`,
   `/api/fires/near/{zip}`, `/api/today/{zip}`, `/api/compare`, `/api/methodology/stats`
   (+ `/api/manifest`, `/api/health`). Parameterized SQL templates over DuckDB, input-
   validated, never free-form. Each tool simply calls its public function — the agent
   cannot cite a number without a replayable URL.
3. **The agent loop.** Server-side tool-use, `claude-fable-5` (fallback
   `claude-sonnet-4-6`), max 5 tool rounds, system prompt `docs/AGENT.md`. SSE progress
   events, one per tool call (the investigation made visible). Token streaming is
   polish-tier only, after RUBRIC is green.
4. **The Fire Weather Report.** Rendered, shareable, every figure linked to its API URL:
   era trend + recency grade + event card (Tubbs percentile) + fuel context + the NRI
   contrast — each claim one of the canonical shapes in CLAUDE.md.
5. **CONSUMER_BINDING spec → implementation.** The eight bindings become real code; the
   consumer iterates `metric_domains`; a pending metric renders "data pending — blocked on
   {blocked_on}", never a broken layer or zeros.
6. **The non-blocky GIS map** (`/explore`, supporting view, never the landing surface):
   continuous **cell field** (824, native 0.25°) beneath **ZIP boundaries** (click-to-read
   aggregated value) with **event points/perimeters** overlaid and a **bivariate** encoding
   (hazard color × exposure saturation from `priority_matrix`). Render fuel as a continuous
   field beneath ZIP, not a flat fill. County→ZIP drill; perimeter click resolves `fire_id`
   to its event card. One fixed color scale across drill levels.
7. **GEE backfill — the raw-weather DATA task** (can run in parallel; it's a data job, not
   app code). The pending `vpd`/`cdd`/`dry_wind_days` need ERA5 daily fields (t_max,
   td_mean, precip, wind u/v). The CDS harvest is the slow path; Google Earth Engine ERA5
   is the build-day path for wind especially. Land the dailies → re-run `05_aggregates` →
   re-export → the metrics promote `pending→served` with zero consumer change. Wind is m/s;
   baseline 1980–2000 vs 2010–present; never reimplement FWI locally.

---

## PART 3 — PENDING DECISIONS (resolve explicitly; honest-or-drop)

Each is a DECISION, not a task to silently code around. The constraint is the same every
time: **source it honestly, or drop the claim — never fabricate.** Tracked in STATE.md §5.

1. **Hazard-axis switch (matrix).** The committed `zip_priority_matrix` uses `fwi_level` =
   recent-era **mean** FWI. The headline credibility story is about high-**percentile** days
   (tails — Tubbs 0.962). DECIDE: switch the hazard axis to a high-percentile-day count to
   unify with the headline (re-sorts some ZIPs, re-exports the matrix), or keep mean and
   document why. Until decided, the matrix is committed-and-stable on mean.
2. **`structures_destroyed` (100% NULL).** The canonical claim + acceptance criterion want
   "5,636 structures." DECIDE: source it as a **cited, labeled constant** (provenance-tagged,
   clearly not from the spine) or **drop** the structures claim. NEVER back-fill as computed
   data — no gate currently catches that fabrication (meta-validation M4).
3. **`erc_pctile` (100% NULL).** VARIABLES.md says ERC percentile is "shown on event cards."
   DECIDE: compute it from the spine (the ERC LUT machinery exists) or drop it from the
   event-card spec. Until then a consumer shows "—", never a filled value.
4. **`zip_trends.robust` (100% NULL).** The era-trend claim shape references a "robust"
   flag. DECIDE: populate the robustness flag in `05_aggregates` or drop it from the claim
   shape. A consumer must NOT read NULL as "not robust" (absence ≠ false).
5. **Fuel `dominant_class` on no-raster ZIPs.** The 22 `total_px=0` ZIPs carry
   `dominant_class="non_burnable"` but have no fuel data — should be NULL/"no_data" (split
   `fuel.py`'s `else` on `total`), distinct from the 12 covered-but-nonburnable that
   correctly stay "non_burnable". Composition is already NULL-correct; only the label remains.
6. **NULL-provenance gate.** No committed check rejects a NULL being silently replaced with
   a plausible value. ADD a gate pinning the all-NULL set (structures/erc/robust) at 100%
   NULL so a future fabricating fill flips RED. Touches write-locked `tests/` → named turn.
7. **Value oracle (the deepest gap).** The suite validates FORM and resolution honesty, not
   arithmetic truth — a shifted grid or wrong-but-in-range percentile passes green. Extend
   the hand-oracle pattern (Tubbs percentile recomputed from the raw spine; a known-(lat,lon)
   →GEFF-cell anchor) to 2–3 more load-bearing numbers, or record as a KNOWN LIMITATION.

---

## PART 4 — FIXED vs FLEXIBLE (what you can change freely; what you must not break)

**FLEXIBLE — workshop freely:**
- Which analytics/claim *combinations* a report leads with; report layout, copy, ordering.
- Map UI/UX: color ramps (within one fixed scale across drills), layer toggles, interaction,
  bivariate styling, animation of *legitimately* time-varying data (the annual series).
- Agent prompt phrasing, tool-call ordering, the number of report sections, streaming polish.
- Which pending metrics to prioritize landing first; the GEE-vs-CDS path for the backfill.
- New **descriptive, non-composite** metrics via the registry (one fn + one entry).

**FIXED — do not break:**
- The served metric set and the never-list (no forecasts/spread/parcel/composite indices).
- The grains and the no-false-precision rule (no sub-cell interpolation, no parcel claims).
- The DuckDB-is-generated invariant (source = parquet; rebuild, never hand-edit; binary
  gitignored).
- The coherence contract: consumers read `metric_domains`; NULL ≠ 0; no snapshot on a time
  axis; no era-comparison drawn as a continuous line.
- The provenance boundary (no squash/backdate; data pre-event, app at-event).
- The validation gates staying green and the honest-or-drop rule for claim-without-data.
- NRI as contrast not validation; the matrix as a categorical quadrant, never a blended score.

If a desired feature requires breaking something in the FIXED column, that's a **DECISION
CHALLENGE** (cite the doc), not a quiet workaround.
