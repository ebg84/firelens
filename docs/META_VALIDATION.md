# META_VALIDATION.md — does the validation have teeth?

A validation suite that cannot fail isn't validating. This audits the **validation
process**, not just the data: every critical gate is mutation-tested (inject the failure
it's supposed to catch, confirm it goes RED), every product requirement is mapped to the
check that covers it, every join's post-join MEANING is justified, and the soft spots are
named honestly. Re-run the mutation harness: `python prep/meta_validate.py` (read-only
w.r.t. the served layer — it operates on a symlink mirror in a temp dir).

Baseline at audit time: **91 passed / 7 pending** (the 7 are `test_dailies.py`, blocked on
the ERA5 harvest — correctly RED, not a regression).

---

## LAYER 1 — Mutation test: which checks have teeth, which are theater

Each row injected the exact failure the gate exists to catch, into a **copy**, then ran the
**actual committed check**. RED = the corruption was caught (teeth). The negative control
(rewrite unchanged) stays GREEN, proving RED comes from the mutation, not the harness.

| gate | mutation injected | committed check | result |
|---|---|---|---|
| orphan ZIP | drop 95404 from zip_cell_map | `validate.check_zip_cell_map` | **TEETH** |
| key alignment (GEOID) | 4-digit ZIP in zip_trends | `validate.check_cross_metric_key_alignment` | **TEETH** |
| key alignment (set) | 4-digit ZIP in zip_trends | `test_domains.test_served_zip_metrics_match_canonical_set` | **TEETH** |
| range bound (date) | 2099 ign_date | `validate.check_temporal_ranges` | **TEETH** |
| range bound (date) | 2099 ign_date | `test_domains.test_fire_events_point_to_cell_in_range` | **TEETH** |
| denom-correct agg | bare-sum instead of weighted-average | `test_nri.test_intensive_uses_denominator` | **TEETH** |
| fraction-sum-to-1 | shrub_frac +0.3 (sum→1.3) | `test_fuel.test_burnable_composition_sums_to_one` | **TEETH** |
| range bound (value) | wfir_risks=250 (>100) | `test_nri.test_wfir_ranges_sane` | **TEETH** |
| range bound (value) | season_len=9999 (>366) | `test_aggregates.test_annual_sanity` | **TEETH** |
| weights-sum-to-1 | halve 90272 weights (sum→0.5) | `validate.check_zip_cell_map` | **TEETH** |
| **NULL-not-fabricated** | fill null fwi_pctile=0.5 **+ fabricate structures_destroyed=5636** | ALL fire_events gates | **THEATER (GAP)** |
| negative control | rewrite zip_cell_map unchanged | `validate.check_zip_cell_map` | GREEN ✓ (expected) |

**10 gates proven to have teeth. One real gap (below).** No check that should have caught a
corruption stayed green except the null-fabrication class.

### The one gap — null→fabricated value is unguarded (and it matters here specifically)
No committed check rejects a NULL being silently replaced with a plausible in-range value.
The range checks only test `where x is not null`, so a fabricated `fwi_pctile=0.5` passes.
This intersects a **product requirement directly**:

- `structures_destroyed` is **100% NULL (3205/3205)**. Yet CLAUDE.md's canonical claim shape
  is *"the Tubbs Fire … destroyed 5,636 structures"* and the report acceptance criterion is
  *"event card with percentile + structures."* The number the product wants to show has **no
  backing column**, and **nothing in the suite would flag** a hardcoded 5636 appearing there.
- That is the single sharpest contradiction between the auditability thesis ("every number
  retrieved from an auditable open dataset") and the data as built.

**Proposed fix (a decision, not auto-applied — see Layer 4 / HALT):** add a provenance gate —
(a) assert `structures_destroyed` is either fully sourced or declared `pending` in the
manifest (no partial/hardcoded fill), and (b) for columns with legitimate nulls (fwi_pctile
×4), pin the null COUNT in a check so a future "fill" flips it RED. This touches `tests/`
(write-locked) and the manifest contract → surfaced for approval, not changed overnight.

---

## LAYER 2 — Requirement → check coverage matrix

What the data layer MUST support (from the acceptance criteria + the canonical claim shapes),
mapped to the check(s) that cover it. ✅ covered & mutation-proven · ⚠️ partial · ❌ gap.

| # | requirement (what the demo/product needs) | covering check(s) | status |
|---|---|---|---|
| R1 | era trend (fwi/season_length/dc_pctile) served at all 1,801 ZIPs | test_domains.test_served_zip_metrics_match_canonical_set; test_export.test_zip_trends_served_metrics; validate #2 | ✅ proven |
| R2 | cell→ZIP weather join resolves; weights sum 1.0; no orphan ZIP | validate.check_zip_cell_map; test_geography (×2) | ✅ proven (M1,M8) |
| R3 | Tubbs anchor ≥0.90 (event-pairing credibility) | test_pairing.test_tubbs_anchor; test_export.test_tubbs_survives_export | ⚠️ threshold only, not value (see L4) |
| R4 | fire_events fwi_pctile ∈ [0,1]; F2 era split clean | test_pairing (×3) | ✅ proven (date range M3) |
| R5 | ignition-percentile histogram / methodology stat ("X% above 80th") | — computed at query time; no stored-artifact check | ⚠️ relies on R4 integrity |
| R6 | NRI intensive=avg-w/-denominator, extensive=allocate | test_nri.test_intensive_uses_denominator | ✅ proven (M5) |
| R7 | NRI 1,693 coverage with explained 108 gap | test_nri.test_no_unexplained_coverage_gaps; test_domains | ✅ proven |
| R8 | matrix quadrants categorical (not a score); Death Valley=monitor | test_priority_matrix (×4) | ✅ |
| R9 | fuel fractions sum to 1; coverage; non-burnable separate | test_fuel (×5) | ✅ proven (M6) |
| R10 | manifest rowcounts match parquet; data/ <100 MB | test_export (×3) | ✅ |
| R11 | granularity honesty (no finer-than-declared time axis) | validate #5; test_domains.test_temporal_granularity | ✅ |
| R12 | pctile_lut monotonic, complete, weekly | test_aggregates.test_lut_monotonic | ⚠️ shape only, not value (see L4) |
| R13 | recency percentile (last-N-yr window rank) | — query-time over R12 LUT | ⚠️ relies on R12 |
| R14 | **event card "structures destroyed"** | — | ❌ **data 100% null; no source** |
| R15 | **no null→fabricated value (auditability thesis)** | — | ❌ **gap (M4)** |
| R16 | live "today's percentile" backed by pctile_lut | app/live.py (event-built); pctile_lut here | n/a (app layer) |

**Coverage gaps:** R14 (structures — missing data + no guard), R15 (fabrication — no guard).
**Effort possibly misdirected / vacuous checks:**
- `validate.check_denorm_regenerable` (#7) — **vacuous today**: no denorm table exists, so it
  passes unconditionally. It's a ready gate, but currently tests nothing. Honest to label it
  N/A rather than count it toward "7/7 green."
- `validate.check_no_cross_domain_leakage` (#6) — **thin**: it only asserts the matrix table
  carries no `date`/`year` column. That's a proxy for temporal coherence, not a verification
  of it (see Layer 3, J5). It passes because the column never existed, not because a join was
  checked.

---

## LAYER 3 — Semantic coherence of every join (meaning, not mechanics)

For each join: what does a value MEAN after it, and is that meaning preserved? Intensive
(rates/scores/indices) must be **averaged**, extensive (counts/dollars) **allocated**, no
snapshot joined to a series as if temporal, no combination across non-overlapping domains.

**J1 · cell→ZIP weather** (`zip_cell_map`, area-weighted).
FWI is an **intensive** climate index. Post-join ZIP value = area-weighted *average* of
overlapping cells → "the typical fire-weather index across this ZIP's footprint." Averaged,
not summed (summing indices is meaningless); weights sum to 1.0 (M8) so it's a true mean.
**Meaning preserved.** Caveat (resolution, not correctness): averaging a coast→inland ZIP
smooths real gradient — mitigated by the render-at-cell-grain / 0.25° floor rule, not by this join.

**J2 · tract→ZIP NRI** (`nri_zip`, residential-weighted).
Two value types, handled differently and correctly (M5 proves the distinction has teeth):
`wfir_risks`/`afreq` are **intensive** → residential-weighted average **with explicit
Σ(res_ratio) denominator**; `wfir_ealt` ($) is **extensive** → bare allocation (Σ of
tract$×res_ratio), conserving dollars. Because RES_RATIO sums to 1.0 per *tract* (not per
ZIP), the denominator is mandatory — a bare sum would deflate every score. **Meaning
preserved:** post-join = "this ZIP's residential-share-weighted hazard score / allocated loss."

**J3 · raster→ZIP fuel** (`fuel_context`, pixel composition).
Pixel counts are extensive; the served fractions are **derived intensive** (burnable px /
total px, and class mix within burnable). Composition sums to 1.0 (M6); non-burnable reported
separately, not buried in the denominator. **Meaning preserved:** a correctly-normalized
proportion. Known *presentation* caveat: `dominant_class` on a low-burnable urban ZIP is
misleading (a 1% sliver reads "timber") — guarded by showing composition only where
burnable_frac is substantial. The data is coherent; the guardrail is a display rule.

**J4 · point→cell fire events** (nearest-centroid snap).
An ignition point snaps to its nearest 0.25° cell to look up that cell's FWI percentile **on
the ignition date** vs the same ISO-week climatology. **Temporally honest** (date→date; no
snapshot-vs-series error). Measured snap distance: median 9.8 km, **max 17.5 km** (< half a
cell; never approaches the 22 km bound). So the percentile is always the *nearest* grid cell's
climatology. **Meaning preserved**, with a bounded caveat: at ≤17.5 km a snap can still cross a
coast→inland gradient — the bound is sub-cell, not a homogeneity guarantee.

**J5 · NRI×FWI matrix** (cross-sectional quadrant).
`fwi_level` (recent-era **mean**, "current") × `wfir_ealt` (2025 snapshot), joined on `zip`.
Both are "current state" → a legitimate **cross-sectional** join; it does **not** pair a 1940
trend point with a 2025 snapshot (that would be the cross-domain error). **Temporal coherence
holds.** ⚠️ But the hazard *proxy* is semantically suboptimal: the headline credibility story
is about high-**percentile** days (tails — Tubbs at 0.962), while the axis uses the **mean**.
A ZIP with extreme tail-risk but moderate mean can be misclassified. Documented as the pending
"mean→tail" fix in ANALYTICS.md — a known proxy weakness, not a silent bug.

**J6 · cell→county, ZCTA→county** (majority-area, inherit-down).
Categorical attribute inheritance; a ZCTA crossing county lines is assigned its majority-area
county (documented precision loss, labeled). Not a value computation. **Meaning preserved.**

---

## LAYER 4 — Honest self-audit: where the process is weakest

**Rigorously verified this pass** (mutation-proven teeth): orphan ZIP, key format, temporal
range, value-range bounds, weights-sum-1, denominator aggregation, fraction-sum-1 — 10 gates.
F1 cell_id internal consistency (0/824 mismatch) and snap distance (max 17.5 km) measured, not
assumed.

**Where I assumed rather than verified — the soft spots, ranked:**

1. **No independent value oracle — the deepest weakness.** Every gate is structural / range /
   coherence. They prove the data is well-*formed* and internally consistent, and now that the
   guards bite. They do **not** prove the numbers are *right*. The Tubbs anchor asserts ≥0.90 —
   it would pass at 0.901 or 0.999 equally; I never hand-recomputed 0.962 from the raw spine.
   `fwi_mean` is checked for >100 distinct values (catches a *fully* broken join, not a subtly
   wrong one). **A spatially-shifted grid, a miscomputed percentile, or a wrong-but-in-range
   value passes everything green.** The only ground-truth anchors are the 5 reference-ZIP
   *county* checks — geography is anchored; **FWI values and percentiles are not.**

2. **F1 grid placement is consistency-proven, not ground-truth-proven.** 0/824 cell_ids
   disagree with their stored lat/lon — but that tests F1 against coordinates F1 itself
   produced. If the source NetCDF coordinate arrays were misread (the calibration step), the
   whole grid could be uniformly shifted and every check stays green. Not re-verified here.

3. **pctile_lut: shape, not correctness.** Monotonic + complete is checked; that p90 is *truly*
   the 90th percentile of the pooled same-ISO-week values is not. Monotonic ≠ correct.

4. **Mutation coverage is one-per-class, not exhaustive.** Not injected: key *type* drift
   (string "95404" vs int 95404 — a classic silent-join killer), duplicate rows inflating a
   weighted average, the `cells_missing_annual` branch of check #1, NaN-vs-null distinctions.
   Each is a plausible real failure I have not yet fired at the gates.

5. **`check_no_cross_domain_leakage` is thin** (Layer 2): it proves absence of a time column,
   not that the join was cross-sectional. I'm relying on the table never having had a time axis.

6. **The null-fabrication gap (M4)** is the one I'd most expect to bite on build day: the
   product *wants* a structures number that doesn't exist, and nothing stops it being faked.

**Single weakest part, stated plainly:** the suite validates **form and resolution honesty**,
not **arithmetic truth**. Post-mutation I can say the guards have teeth and the data is
internally coherent. I cannot yet say every served number is *correct* — there is no external
oracle for FWI values or percentiles, only structural guards and one geography anchor. That is
the gap to close before build day, and it is not closeable by adding more range checks.

**Decision points surfaced (HALT — not changed overnight):**
- (a) Add the null-provenance / fabrication gate (R15) — touches write-locked `tests/`.
- (b) Resolve R14: either source `structures_destroyed` or drop "structures" from the event-card
  claim and acceptance criterion (it currently promises data that doesn't exist).
- (c) Decide whether an independent value oracle (hand-computed Tubbs percentile from the spine;
  a known-(lat,lon)→GEFF-cell ground-truth anchor) is worth building before the event.
