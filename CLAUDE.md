# FireLens — Project Memory

FireLens is an open-source California wildfire climate intelligence
platform. Its primary product is a Claude-powered analyst that investigates
any California ZIP code and produces an evidence-cited Fire Weather Report:
85 years of atmospheric trajectory, the documented fires nearby with the
conditions on their ignition days, fuel context, and today's conditions
ranked against the full historical record — every number retrieved from an
auditable open dataset. An interactive map supports exploration; the
analyst and its reports are the product. FireLens is descriptive by design:
trajectory, record, and present context — never forecasts, loss modeling,
or parcel-level assessment. It is not a RAG application: there is no
retrieval corpus; the agent executes parameterized SQL tools against a
computed analytics layer.

## Documentation index and reading order
This file is auto-loaded every session and doubles as the index. Reading
order: README.md → this file → docs/ARCHITECTURE.md (design, decisions,
**the Decision Ledger — read it before proposing any change of
direction**, and Part 2: development/deployment) → docs/DATA.md (the
entire data layer: Part A sources/access, Part B formulas/DDL, Part C
joins/failures) → docs/AGENT.md (the production system prompt) →
docs/TESTING.md (gates + heuristics) → RUBRIC.md (write-locked,
machine-gradable done). Load on demand via @docs/<name>.md. PLAYBOOK.md
is the developer's external execution doc — not committed, not yours to
require.

## Session modes
**Pre-event sessions (pipeline day and all preparation):** collaborative
and developer-gated. Use plan mode for every script: present the plan in
plain language, wait for approval, implement, run it, show real output.
The developer reviews *behavior*, not code — never ask them to read a
diff as proof; run the thing. Apply TESTING.md's P1–P4 templates as
written (predict-then-run, tests/ locked, smallest safe fix, DECISION
CHALLENGE on contract conflicts, OVER BUDGET past ~30 min).
**Event window (build day only):** the autonomous mode below.

## Communication conventions (always, both modes)
Direct, technically precise, plain language — no hedging, no filler, no
unexplained jargon. Explain every failure in one plain sentence before
fixing it. Surface tradeoffs and assumptions explicitly rather than
choosing silently. When a request conflicts with the locked architecture
or a documented decision, say so immediately and cite the doc. Never
expand scope unrequested; offer additions as options, not faits
accomplis.

## Operating mode: autonomous build with machine-verifiable gates
This project is built by Claude Fable 5 running long-horizon with minimal
human intervention. Conventions:
- "Done" is never self-declared: a task is complete when its acceptance
  criterion below passes AND its TESTING.md tier is green AND the
  RUBRIC.md item can be checked by running a command, loading a URL, or
  grading against the rubric file.
- Use verifier sub-agents: before any milestone is marked complete, a
  fresh-context agent grades the work against RUBRIC.md and the relevant
  TESTING.md tier. The builder does not grade its own work.
- Self-correct from real signals: run tests, read failures, fix, rerun.
  Escalate to the human only via "DECISION CHALLENGE:" (instruction
  conflicts with locked architecture) or "OVER BUDGET" (a fix exceeds ~30
  minutes; propose the smallest viable alternative — pre-approved scope
  reductions, in order: (1) drop FIRMS/FHSZ/fuel overlays, (2) drop the
  map view entirely, (3) reduce chat to two tools with cached responses
  for the five reference ZIPs. The analyst + report NEVER ships without
  being primary; the map is always cuttable, the agent never is — a
  map-only build is the banned dashboard archetype and must not exist.)
- Preserve the session log; it is a submission artifact.
- tests/ and RUBRIC.md are write-locked during implementation; changes to
  either happen only in dedicated, named turns with explicit approval.
- Commit on green with descriptive messages; tag milestone checkpoints.
- Prefer boring, documented patterns over clever ones.

## Locked architecture
1. Two-tier data: heavy tables live in `$FIRELENS_DATA` (local only); the
   deployed app ships only `data/` (<100 MB Parquet + simplified GeoJSON +
   optional fuel PNG). No database server, no auth.
2. **Zero-geometry rule:** the deployed app performs no spatial
   computation. All geometry resolves to keys at pipeline time
   (docs/DATA.md (Part C) J1–J10). Runtime joins are key lookups; the only
   allowed coordinate math is scalar arithmetic (e.g., haversine).
3. Stack: **Python end-to-end.** Prep pipeline: Python + DuckDB +
   GeoPandas (prior work, disclosed). Platform: **FastAPI + DuckDB**
   serving (a) the public REST API, (b) the agent loop (Anthropic SDK,
   server-side), and (c) a static frontend (vanilla JS + MapLibre GL +
   plain HTML/CSS) — one repo, one service, deployed as a container on
   Render (Railway as fallback), auto-deploy from main. **The agent's
   tools and the public API are the same five endpoints** — every figure
   in a report cites a replayable public URL. No JavaScript frameworks, no
   client-side database, no Streamlit (banned), no second language.
4. FWI is consumed precomputed from GEFF-ERA5 via the **EWDS** endpoint
   (not CDS). FWI equations are never implemented locally. `cell_id`
   derives from each file's actual coordinate arrays (calibration F1).
5. Occurrence dedup (F2): statistics use FPA-FOD exclusively 1992–2020,
   FRAP exclusively 2021+; FRAP geometries display for all eras.
6. **v1 served metric set + Metric Extension Protocol** (restructured
   2026-06-12 from a closed enum): the **as-built served set** is `fwi`,
   `season_length`, `dc_pctile`; `vpd`, `cdd`, `dry_wind_days` are declared
   `pending` (blocked on the ERA5 harvest/wind, folding in by re-export). New
   **descriptive, non-composite** metrics may be added through the registry
   (`prep/metrics.py`): one formula function + one registry entry, with
   LUTs/aggregates/trends/export iterating the registry generically (never
   naming a metric). The never-list (forecasts, fire behavior/spread,
   parcel, composite/invented indices) stays a hard boundary —
   extensibility lives strictly inside it, single descriptive measures
   only. Wind is m/s (Open-Meteo defaults to km/h — request m/s). Baseline
   1980–2000 vs 2010–present. ZIP annual series = `zip_cell_map`-weighted
   averages at query time.
7. Fuel context (optional, LANDFIRE FBFM40): composition + burnable
   fraction per ZIP; categorical handling only; never multiplied into
   weather metrics; no composite index.
8. Map (supporting view, never the landing surface, never framed as the
   main feature — the app's `/` route is the analyst/report input; the
   map lives at `/explore`, linked from report citations; the word
   "dashboard" appears nowhere in UI copy, code identifiers, or docs):
   county
   choropleth → lazy per-county ZIP polygons; FRAP ≥1,000 ac with decade
   toggle (fire_id property required); FIRMS density via heat layer; FHSZ
   and fuel as toggles; one fixed color scale across drill levels.
9. Agent: server-side tool-use loop, model `claude-fable-5` during the
   event (fallback `claude-sonnet-4-6`), max 5 tool rounds; tools are
   parameterized SQL templates with input validation — never free-form
   SQL — and each tool simply calls the corresponding public API
   function. System prompt: docs/AGENT.md. Primary surface: chat + a
   rendered, shareable Fire Weather Report per location, every figure
   linked to its public API URL.
9b. **Public REST API (day-one deliverable, the open substrate):**
   GET /api/trends/{zip} · /api/fires/near/{zip}?radius_km= ·
   /api/today/{zip} · /api/compare?zips= · /api/methodology/stats ·
   /api/manifest · /api/health. JSON, CORS-open for reads, documented by
   FastAPI's auto-generated /docs (OpenAPI). Streaming rules: report
   generation emits SSE progress events (one per tool call — the
   investigation made visible); token streaming is polish-tier only,
   attempted solely after RUBRIC is green, never an acceptance
   criterion. Live data feeds/webhooks and bulk-stream endpoints are out
   of scope — bulk access is the repo itself (documented one-liner).
10. `data/manifest.json` is the pipeline↔app contract; the app validates
    it at load and fails loudly on mismatch.
11. Out of scope, do not propose: ML fire-probability models, fine-tuning,
    parcel-level features, user accounts, composite risk indices,
    statewide gridMET or LANDFIRE-as-join-unit, forecasting, live pipeline
    re-runs during the event (data layer is prior work, period), and anything
    on the event's prohibited list (incl. Streamlit, dashboard-first
    framing, RAG patterns).

## The analytics layer, by example (canonical claim shapes)
Every sentence FireLens produces is one of these shapes, and every shape
traces to a specific table and column. Build toward these outputs;
anything that doesn't reduce to one of them is drift.

- **Era trend** — "95404 averages 14.3 Red Flag-condition days/yr in
  2010–present vs 10.0 in the 1980–2000 baseline: **+43%, and extreme
  days come 2.1× as often.**" ← zip_trends(baseline, recent, pct_change,
  freq_ratio, robust); computed per the v1 served set.
- **Season length** — "the fire-weather season here runs **~24 days
  longer** than in the baseline era." ← annual_metrics.season_len →
  zip_trends.
- **Recency grade** — "the last five years rank in the **96th percentile
  of every five-year window since 1940** at this location." ← rolling
  windows over annual_metrics.
- **Event pairing** — "the Tubbs Fire ignited Oct 8, 2017 on a day in
  the **97th percentile of 85 years** of fire weather here, and
  destroyed **5,636 structures**." ← fire_events(fwi_pctile,
  structures_destroyed, cause_class).
- **Live ranking** — "today ranks **between the 90th and 95th
  percentile** for mid-June at this location." ← Open-Meteo forecast
  endpoint value bracketed against pctile_lut (max-weight cell, ISO week).
- **Comparison** — "Red Flag days have grown **2× faster in 95404 than
  in 94588** since the baseline era." ← compare_locations over
  zip_trends.
- **Validation** — "**[X]% of large fires ignited above the 80th
  percentile** of our metrics, vs 20% by chance." ←
  get_methodology_stats over fire_events.
- **Fuel honesty** — "the atmospheric trend is real here, but only
  **12% of this ZIP carries burnable fuel**." ← fuel_context
  (burnable_frac), volunteered when low.

**Never-shapes (anti-examples — these indicate drift, stop and raise
DECISION CHALLENGE):** year-over-year deltas ("up 14% vs last year" —
single years are weather; eras are climate; the schema cannot even
express YoY and must stay that way); any future-tense number ("will
rise," "by 2030"); any parcel-level claim; any composite risk score; any
spread/behavior characterization.

## Event constraints (Claude Fable 5 Build Day)
Public repo mandatory. All demoed code is built during the event window
(10:30–17:00); submission at 17:00 sharp includes a 1-minute demo video,
the brief (this repo's docs), RUBRIC.md, and the session log. Scoring:
Impact 35, Demo 35, Autonomy 15 (fewest human interventions, self-caught
failures), Orchestration 15 (repeatable setup, machine-verifiable done).

## Repository map
- `app/` — FastAPI application: `main.py` (routes), `api/` (the five
  query endpoints + manifest/health), `agent.py` (tool loop), `live.py`
  (Open-Meteo forecast endpoint with past_days; America/Los_Angeles
  dates; m/s), `static/` (index = analyst/report page, explore = map
  page, MapLibre + vanilla JS), `templates/` (report rendering)
- `data/` — serving layer only · `prep/` — Python pipeline (never
  imported by the app) · `tests/` — TESTING.md tiers (pytest for
  pipeline; script/URL checks for app) · `RUBRIC.md` — machine-gradable
  completion rubric · `docs/` — ARCHITECTURE.md, DATA.md, AGENT.md, TESTING.md per the index above

## Commands
- Pipeline: `python prep/0N_*.py` in order; gates refuse on red
- App: `uvicorn app.main:app --reload` · Deploy: push to main (Render
  auto-deploys) · Tests: `pytest -q` (fast: `pytest -m fast`)
- Secrets: `ANTHROPIC_API_KEY` in Render environment variables and
  `.env` (gitignored). Never in code or commits.

## Acceptance criteria (a milestone is done when…)
- pipeline: Tiers 1–3 green incl. the anchor test; manifest written;
  data/ ≤100 MB
- app skeleton: deployed URL serves /api/health 200 and
  /api/trends/95404 returns real zip_trends JSON; / renders it
- report: entering 95404 renders a cited Fire Weather Report (trend,
  recency grade, Tubbs event card with percentile + structures, fuel
  context if shipped)
- map: county→ZIP drill-down; perimeter click resolves fire_id to its
  event card
- agent: TESTING.md Tier 4 golden questions 1–6 and the three adversarial
  declines pass on the deployed URL
- live: today's percentile for 94588 from a browser call, correct local
  date
