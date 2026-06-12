# docs/TESTING.md — FireLens testing specification & process

> **Reading order:** 6 of 7 · **Depends on:** DATA.md (Part B) (formulas under test); DATA.md (Part C) (F/J registries it gates); AGENT.md (behavior its Tier 4 verifies); DATA.md (Part A) (assumptions its Tier 0.5 retires)
> **Single source of truth for:** all verification gates (Tiers 0–5), the agentic-testing heuristics (H1–H6), and the implementation prompt templates (P1–P4)
> **Forward references:** none — this is the terminal verification document
Philosophy: the developer reviews *behavior*, not code. Every tier below
produces output a reviewer can reviewer without reading the implementation. Claude Code writes and runs the
tests; the developer read the green/red summary and the printed numbers.

## Process rules
1. Tests live in `tests/` (pipeline: `tests/prep/`, app: `tests/app/`),
   runner: `pytest -q`. Tiers tagged with markers: `pytest -m tier2`.
2. **Definition of done = the module's acceptance test in CLAUDE.md passes
   AND its tier here is green.** Claude Code must run the relevant tier after
   every module and paste the output before claiming completion.
3. Pipeline tests run the pipeline phase and gate the serving-layer export: the export
   script refuses to write `data/` if Tier 1–3 fail (a literal
   `assert run_checks()` at the top of `prep/06_export_serving.py`).
4. Build day: Tier 0 at the venue first thing; Tier 4 after each app module;
   Tier 5 (demo rehearsal) at the rehearsal gate. Commit only on green.
5. Any red test gets ONE 30-minute fix attempt, then invoke the relevant cut
   line rather than debugging into the demonstration window.

## Tier 0 — Environment smoke (5 min; run at install time and at the venue)
- `python -c "import duckdb, geopandas, anthropic, fastapi"` (one env)
- a minimal FastAPI app serves locally via `uvicorn`; /docs renders
  exits 0 on the pinned versions in requirements.txt.
- `duckdb.sql("select 1")` works; a sample Parquet queries from disk.
- Anthropic API round trip: one Messages call returns; key loads from
  `.env.local` / Render env vars, never from code or the client bundle.
- `git push` → Render deploy completes; deployed /api/health returns 200.

## Tier 0.5 — Tracer-bullet protocol (first-contact calibration)
Before any bulk acquisition, retrieve a minimal sample from each remote
source end-to-end and retire every [ASSUMPTION] in DATA.md (Part A) that
only contact with a real file can resolve:
- GEFF/EWDS: one month of FWI — request schema accepted, NetCDF opens,
  FWI variable name confirmed, and `cell_id` derived from the file's own
  lat/lon arrays (calibration F1 in DATA.md (Part C); the v4.1 grid differs
  from prior versions, so the lattice is never assumed).
- ERA5 daily statistics (CDS): one month — same checks.
- Open-Meteo: one historical call (`wind_speed_unit=ms` honored; daily
  parameter names as documented) and one forecast-endpoint call with
  `past_days` (confirms the live path's data recency — calibration G12).
Bulk requests are queued only after the tracer passes. Expected cost:
~30 minutes. Failures here are configuration findings, not defects.

## Tier 1 — Acquisition validation (run after each download, during the acquisition phase)
For every raw dataset, an automated check prints a one-line PASS/FAIL:
- GEFF FWI: opens with xarray; **grid registration (F1): cell_id derives
  from the file's actual lat/lon arrays, and Open-Meteo centers match them
  exactly**; bbox covers 32–42.1°N / -124.5–-114°W; date
  range 1940-01-01 → within 60 days of today; FWI values in [0, 150];
  <1% NaN over land cells after 1950.
- ERA5/Open-Meteo dailies: per cell, ≥95% of expected days present per year;
  temp in [-40, 60] °C; dewpoint ≤ temp on ≥99.5% of days; precip ≥ 0.
- FPA-FOD: CA records ≥ 150,000; DISCOVERY_DATE parses for ≥99%; lat/lon
  inside CA bbox for ≥99.5% of CA-tagged rows.
- FRAP: ≥ 15,000 perimeters; ALARM_DATE non-null for ≥90% of post-2000
  records; GIS_ACRES > 0; known anchors exist by name+year: TUBBS 2017,
  CAMP 2018, AUGUST COMPLEX 2020, **and — anchor-critical — PALISADES 2025
  and EATON 2025** (the spring-2026 FRAP release should contain 2025; if
  absent, pull the 2025 perimeters from NIFC/WFIGS Open Data the same
  hour — named fallback, not a build-day surprise).
- FIRMS: CA detections ≥ 1,000,000 (2000–present); per-row date parses;
  confidence fields match expected schemas for MODIS vs VIIRS.
- TIGER: CA ZCTA count in [1600, 1900]; all geometries valid
  (`geom.is_valid`), none empty.
- Top 20 impact table (micro-stretch): ≥15 of 20 rows join to
  fire_events by (name, year); TUBBS and CAMP totals match the official
  published list exactly (keying check).
- LANDFIRE FBFM40 (stretch): raster opens in EPSG:5070; pixel values are
  ONLY legal FBFM40 codes (catches wrong resampling, F10).

## Tier 2 — Unit tests on formulas & transforms (written WITH the pipeline)
Exact-value tests, tolerances stated:
- Magnus/RH: T=30°C, Td=10°C → RH ≈ 28.9% (±0.5); T=Td → RH=100;
  VPD(T=35, Td=5) ≈ 4.75 kPa (±0.05); VPD floor: Td>T input → VPD=0.
- Red Flag day: (wind_max=12 m/s, RH_min=20) → True;
  (10.9, 20) → False; (12, 26) → False. Boundary values land as specified.
- CDD: synthetic series Dec 20–Jan 15 dry → single run of 27 crossing the
  year boundary, assigned to the later year; a 0.9 mm day counts dry,
  a 1.0 mm day does not.
- ISO-week binning: 2017-10-08 → week 40; Dec 29–31 of a 53-week year maps
  to bin 52.
- Percentile LUT properties (every cell): all 11 thresholds (deciles +
  p95/p99) strictly increasing; no NULLs; percent_rank of the historical max = 1.0.
- ZIP mapping: every CA ZCTA has ≥1 cell; weights per ZIP sum to 1.0
  (±1e-6); spot ZIPs land in the right county: 95404→Sonoma, 90272→
  Los Angeles, 94588→Alameda.
- Pairing: a synthetic ignition at a cell centroid on a known date returns
  exactly that cell and that day's FWI.
- UNITS (the km/h trap): statewide annual mean of wind_max lies in
  [2, 15] m/s; a value near 3.6x that range fails loudly.
- Dedup (F2): zero duplicate fire_ids; statistics contain no FRAP records
  dated <2021 and no FPA-FOD records dated >2020.
- Manifest: data/manifest.json schemas match the written Parquet exactly;
  lib/db.py startup check fails loudly on an injected mismatch.

## Tier 3 — Scientific sanity (the "would an expert nod" suite; the pipeline phase gate)
Each is a single query + assertion with the expected direction stated:
- ANCHOR EVENTS: Tubbs (2017-10-08, Sonoma cells) FWI percentile ≥ 0.90;
  Palisades/Eaton (2025-01-07/08, LA cells) Red-Flag = True and FWI
  percentile ≥ 0.90. **Degradation clause:** if the FWI path is dark, the
  anchor asserts VPD-percentile ≥ 0.90 + Red-Flag = True instead — the
  anchor test never goes untested. THE single most important test in the project — if it
  fails, nothing else matters until it passes.
- SEASONALITY: statewide mean FWI for Jul–Oct > 2× mean for Dec–Mar.
- GEOGRAPHY: mean annual Red-Flag days, inland Southern CA cells > coastal
  Northern CA cells.
- TREND DIRECTION: statewide mean VPD_max, 2010–present > 1980–2000 (any
  other result means a units/join bug, not a climate surprise).
- FIRE-WEATHER LINK: Pearson r between annual statewide fire-weather-day
  count and annual FRAP acres burned (1990–2024) > 0.3.
- VALIDATION HISTOGRAM: share of paired ignitions (≥300 ac) above the 80th
  percentile ≥ 40% (i.e., ≥2× the 20% chance rate); print the actual number
  — it goes in the presentation.
- SEAM (F2): annual paired-event counts across 2019-2022 show no cliff or
  spike at the 2020/2021 source boundary beyond real-world variation.
- FUEL GEOGRAPHY (stretch): a Mojave desert ZIP has burnable_frac < 0.2; a
  Sierra timber ZIP > 0.6; statewide burnable_frac varies (not constant).
- NON-DEGENERACY: every metric varies — no county where all ZIPs share an
  identical pct_change (smells like a broken join).

## Tier 4 — App integration (build day, after each module)
- DB: `get_trends('95404')` returns all 5 metrics in <1 s; unknown ZIP
  returns a typed NotFound, not an exception.
- Map: county GeoJSON loads <2 s; **no visible slivers/gaps between
  adjacent ZCTAs at drill-in (G8 — topology check, visual)**; the FIRMS
  HeatMap renders from firms_density rows (G1); county and ZIP views use
  identical color breakpoints (G2); clicking Sonoma loads only Sonoma ZCTAs;
  clicking 95404 renders the trend panel + sparkline; clicking the Tubbs
  perimeter shows its event card with the percentile; the clicked
  feature's fire_id property resolves to a fire_events row (J12/F5).
- Tools (all five: get_trends, get_fires_near, get_today_context,
  compare_locations, get_methodology_stats): each returns schema-valid
  JSON for the 5 reference ZIPs;
  input validation rejects `"' OR 1=1"`, `"00000"`, `"not a zip"` with a
  human-readable message; tools NEVER interpolate raw user strings into SQL.
- Agent loop GOLDEN QUESTIONS (run all 5; a pass = answer cites ≥2
  tool-returned numbers and respects guardrails):
  1. "Should the client buying in 95404 worry about October?"
  2. "Compare fire weather trends in Napa vs Pacific Palisades."
  3. "What fires have happened near 95404 and what were conditions like?"
  4. "Is today dangerous in 94588?" (must trigger the live tool)
  5. "Why should I trust this?" (must call get_methodology_stats)
  6. "How risky is fire weather in a desert ZIP like 92328 (Death
     Valley)?" (must note real atmospheric trend + minimal burnable fuel,
     unprompted, if fuel_context shipped; else states the 31 km caveat)
  Plus 3 adversarial: "Should I buy this house?" / "What insurance should I
  get?" / "Exact risk for 123 Oak St?" → declines with the resolution caveat,
  offers what it CAN provide.
- Live tool (G12): get_today_context uses the forecast endpoint, returns
  a percentile in [0,1] for 94588 with the data date labeled and within
  the last 48 h; on
  a forced network failure, the app shows the graceful-degradation message,
  not a traceback.
- Deployed parity: golden question #1 passes on the LIVE URL, not just local.

## Tier 5 — Pre-release verification protocol (the rehearsal gate)
- Run the demonstration runbook (external) start-to-finish 3× on the deployed URL; time each (<3:30).
- Failure drills, once each: kill Wi-Fi mid-demo → local fallback within
  60 s; simulate API failure → cached responses for the 5 reference ZIPs appear.
- Capture a screenshot of every demo beat into the demonstration runbook (external) as the final backup.
- Freeze: after rehearsal 3, only red-test fixes may be committed. No
  unforced changes in the last 30 minutes.


---

# PART 2 — Testing heuristics & the Claude Code prompt playbook
Part 1 defines WHAT is tested (the tiers/gates). Part 2 defines HOW testing
is conducted when the implementer is an AI agent and the system is a data
pipeline with no per-value ground truth. Six heuristics, then the prompt
templates that operationalize them.

## H1 — Tests-first, tests-locked (the agent-trust heuristic)
The strongest known pattern for agentic coding is inverted TDD: tests are
written FIRST, confirmed to fail, **committed as a checkpoint**, and only
then is implementation written under the instruction "do not modify the
tests." The commit matters because agents will sometimes alter tests to
make them pass rather than fix code — the git diff makes any such change
visible and revertible. FireLens rule: `tests/` is write-locked for the
agent during implementation passes; test edits happen only in dedicated
test-writing turns, named as such, and are committed before implementation
begins.

## H2 — Test the test (fault injection)
An AI-written test that has never failed is unverified — vacuous tests
(asserting truisms, hardcoding observed outputs) are a known agent failure
mode. Every gate test must be demonstrated to FAIL on injected bad data
before it counts (the suite already does this for F2; T8's
inject-violation-then-detect pattern is the template). Rule: a new gate
test's definition-of-done includes one shown failure.

## H3 — The oracle problem → three substitutes
A 22M-row climate table has no answer key; per-value correctness is
unknowable. Scientific pipelines substitute three test types, all already
seeded in Part 1 and now named as the deliberate strategy:
- **Known-answer anchors** (Tier 3 Tubbs/Palisades): a handful of points
  where external reality IS the oracle. Strongest signal, narrowest
  coverage. Never tune code until an anchor passes — find the bug.
- **Metamorphic relations**: where outputs are unknowable, RELATIONS
  between outputs are knowable. If the pipeline is right, then
  necessarily: raising temperature with dewpoint fixed raises VPD
  (monotonicity); shuffling input row order leaves every aggregate
  unchanged (permutation invariance); a ZIP with one cell equals that
  cell's values exactly (degenerate-case identity); summer FWI > winter
  FWI per cell (domain ordering); weights × anything conserves totals.
  Cheap to write, enormous bug surface — these catch the unit flips,
  join duplications, and sign errors that anchors miss.
- **Property-based tests** (Hypothesis, formulas only): for the §1 math,
  assert invariants over thousands of generated inputs — RH ∈ [0,100],
  VPD ≥ 0, es(T) strictly increasing, cell_id round-trips for random CA
  coordinates. Scope-capped to pure functions; never applied to pipeline
  I/O (too slow for the prep window).

## H4 — Golden data (characterization for the serving layer)
After the pipeline phase's gates pass, snapshot the complete serving-layer rows for
the 5 reference ZIPs into `tests/golden/`. From then on, any pipeline change
must either reproduce the golden rows exactly or come with a written
explanation of why they changed. This converts "did the refactor silently
shift the demo numbers?" from anxiety into a diff — and it is the direct
adaptation of characterization testing to a data product: the locked
behavior is the DATA, not the code.

## H5 — Writer/Reviewer separation (fresh-context audit)
A fresh context reviews better than the one that wrote the code, because
it isn't biased toward its own output. At each build-day gate (post-map,
post-agent), open a fresh Claude Code session (or /clear) whose only task
is audit: "The developer did not write this code. Review lib/tools.py against
@docs/DATA.md §4.5 and @docs/DATA.md for contract
violations, then run the full suite." Same model, uncorrelated errors.

## H6 — Two-speed suite (the clock heuristic)
Long suites get skipped under time pressure. Split:
`pytest -m fast` (<30 s: formulas, schema/manifest, tool validation,
metamorphic relations on sampled data) runs after EVERY module;
the full suite (Tier 1–3 data scans, golden comparisons, agent goldens)
runs only at the three gates (pipeline export, post-map, post-agent).
Speed is a feature of tests; slow tests are skipped tests.

## The prompt playbook (prompt templates)
Use verbatim in Claude Code; each encodes the heuristics above.

**P1 — Red/green cycle (adapted sample #1 + H1/H2 + predict-then-run):**
"Run `pytest -m fast`. BEFORE running, predict pass/fail per test and
state why. For each failure: (1) exact cause in one plain sentence,
(2) smallest safe fix — in implementation code only; tests/ is locked,
(3) rerun and show output. If the developer believe a TEST is wrong, stop and say
DECISION CHALLENGE with reasons. Never disable, skip, or weaken a test.
If the failure reveals an uncovered edge case, propose the new test;
the developer approves before the developer add it. Plan before editing."
(The predict-then-run step exposes miscalibration: a wrong prediction is
a signal the agent doesn't understand the module — stop and replan.)

**P2 — Safe refactor (adapted sample #2 + H4):**
"Before refactoring [module]: confirm the golden serving-layer snapshots
and `pytest -m fast` are green and committed. Refactor in small commits,
one logical change each. After each commit, rerun fast + golden
comparison. Any golden diff = stop, show the diff, explain, wait for my
approval. Call out suspected behavior-edge changes proactively."

**P3 — Scenario generation (adapted sample #3, run after pipeline gates pass for
app.py before it exists):** "From @docs/ARCHITECTURE.md
§4 and @docs/the demonstration runbook (external), enumerate every user flow and failure point for the
app: normal flows (county click → ZIP click → perimeter click → chat),
edge inputs (PO-box ZIP, out-of-state ZIP, SQL-ish strings, empty chat,
double-clicks mid-load), degraded states (FWI absent, fuel_context
absent, live API down, manifest mismatch). Output a checklist mapped to
existing Tier 4 tests; flag scenarios with NO covering test — those are
developer approval queue, not the to-do list."

**P4 — Post-edit audit (adapted sample #4 + H5, fresh session):**
"The developer did not write this code. Audit [module] against its contracts
(@docs/DATA.md, @docs/DATA.md, CLAUDE.md guardrails)
for: contract violations, silent side effects on other modules, broken
imports, test-weakening in the diff since [tag]. Run the full suite.
Report findings BEFORE fixing anything; fix only on explicit go-ahead. DONE requires
100% pass plus a clean diff review."

## What is deliberately NOT in the methodology
Mutation testing frameworks (mutmut etc.) — H2's manual fault injection
captures the value at 1% of the cost. LLM-as-reviewer for agent answers —
Tier 4's golden questions use deterministic MUST-CONTAIN / MUST-NOT-
CONTAIN string rules instead (e.g., answer to Q2 must contain a period
reference and must not contain "will" + a year); cheap, reproducible,
and sufficient at this scale. CI pipelines — the developer IS the CI
until Sunday; GitHub Actions is a post-build window line.


---

# PART 3 — Autonomous-operation addendum (event rules)
The gates above are unchanged; who runs them changes. In autonomous
operation the builder agent runs every tier itself and a **verifier
sub-agent in a fresh context** grades each milestone against RUBRIC.md
plus the relevant tier before the builder may proceed — the builder never
grades its own work (this is H5, now mandatory rather than advisory).
Wherever Part 2's prompt templates say "developer approval," read
"verifier verdict"; the human is consulted only at the two escalation
triggers defined in CLAUDE.md (DECISION CHALLENGE, OVER BUDGET) or to
supply new information. Every run, failure, self-correction, and verifier
verdict stays in the session log, which is a scored submission artifact —
a failure the model catches and fixes itself is worth more on the record
than a failure that never happens.
