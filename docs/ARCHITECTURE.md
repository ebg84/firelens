# Architecture

> **Reading order:** 1 of 7 (read after README.md and CLAUDE.md) · **Depends on:** README.md (product framing); CLAUDE.md (locked-architecture list it elaborates)
> **Single source of truth for:** system design, decision rationale, blocker/contingency register
> **Forward references:** DATA.md (Part A), DATA.md (Part C), DATA.md (Part B), TESTING.md, ARCHITECTURE.md (Part 2), AGENT.md (each elaborates one layer named here)

FireLens answers three questions for any California ZIP code, from open
data: how the local fire-weather environment has changed across 85 years;
which documented fires occurred nearby and what the atmosphere was doing
on their ignition days; and how present conditions rank against that
location's full historical record. It is an evidence layer — descriptive,
auditable, and free — beneath the closed risk scores the market already
uses. It deliberately does not forecast, model loss, or assess parcels;
the serving layer is designed so that open modeling efforts can build
those layers on top of it.

## System design

```
Open sources → prep pipeline (local) → serving layer (repo) → app → agent
```

- **L0 Sources.** Ten open datasets spanning weather, fire occurrence,
  fuel, exposure, and geography (docs/DATA.md (Part A)). All public
  domain or CC-BY.
- **L1 Prep pipeline** (`prep/`, runs locally, never in production):
  derives daily metrics per atmospheric grid cell, builds percentile
  climatologies, resolves all spatial relationships to keys, pairs fire
  events with same-day atmospheric conditions, and aggregates trends.
- **L2 Serving layer** (`data/`, committed, <100 MB): Parquet aggregates,
  percentile lookup tables, paired fire events, simplified GeoJSON, and a
  `manifest.json` contract. Queried in-process by DuckDB — no database
  server exists.
- **L3 Application** (`app/`): FastAPI + DuckDB in one container
  (Render), serving three things from one process: the **public REST
  API** (the open substrate — /api/trends, /api/fires/near, /api/today,
  /api/compare, /api/methodology/stats, plus /api/manifest and OpenAPI
  /docs), the static frontend, and the agent. The landing route (`/`) is
  the analyst: a location/question input that produces a rendered,
  shareable, citation-bearing Fire Weather Report in which every figure
  links to the public API URL that produced it; a supporting map view at
  `/explore`
  offers the statewide county choropleth with per-county lazy-loaded ZIP
  polygons, fire perimeters by decade, a detection-density heat layer,
  and hazard-zone/fuel overlays — all fetching JSON from the same public
  API. The Parquet serving layer ships inside the deploy and is read
  from local disk by DuckDB.
- **L4 Intelligence** (`app/agent.py`): a Claude tool-use agent (model
  `claude-fable-5`) whose five tools are the same functions behind the
  five public API endpoints — the agent audits identically to any
  external user. The loop runs server-side with the only secret. The
  agent translates plain-language questions into tool calls and composes
  the cited report; it cannot assert a value it did not retrieve
  (docs/AGENT.md). It is not RAG: there is no retrieval corpus — only
  typed queries against a computed analytics layer.

## Design decisions and rationale

**No backend, by construction.** The serving layer ships inside the
repository and is read in-process. Rationale: it removes every
operational failure surface (connections, migrations, auth, scaling) from
a system whose data is small after aggregation (~120k serving rows from
~22M pipeline rows), and it makes data and code version, deploy, and roll
back together — `git push` is the entire release process. **One small
service, deliberately:** a single FastAPI container reading bundled
Parquet via DuckDB is the minimum architecture that can serve a public
query API — and the API is not an add-on but the product's auditability
made concrete: the agent's tools, the frontend's data calls, and any
external researcher's curl command hit the same endpoints, so "every
number is checkable" becomes a hyperlink, not a promise. Python
end-to-end also means the pipeline, API, agent, and tests share one
language and one set of maintainers' skills.

**Zero-geometry rule.** All spatial computation happens once, in the
pipeline, and is stored as foreign keys and weights (the join registry in
docs/DATA.md (Part C)). The deployed app performs key lookups only.
Rationale: geometry is the dominant source of both bugs and runtime cost
in GIS applications; quarantining it to build time means the production
app cannot have a spatial failure.

**Hub-and-spoke resolution handling.** Datasets range from ~31 km
atmospheric grids to 30 m fuel rasters. They are never reconciled
pairwise; each is translated once into shared reference units (grid cell,
ZIP, county, event point) via one of four operations — aggregate up,
inherit down with labeling, area-weighted apportionment, or bounded
snapping — and information flows fine→coarse only. Coarse values are
never disaggregated arithmetically; layering across scales is permitted
visually (a fuel underlay beneath an atmospheric choropleth) but never
multiplied. Rationale: this is the standard crosswalk pattern; it bounds
N datasets at N translations instead of N² reconciliations, and it keeps
every served claim at a granularity the underlying measurement supports.

**Precomputed indices over reimplementation.** The Fire Weather Index is
consumed from the Copernicus GEFF-ERA5 product rather than computed
locally. Rationale: FWI is a stateful system (moisture codes carry across
days) whose correct implementation is a project in itself; consuming the
authoritative product eliminates that risk and strengthens auditability.

**Established thresholds over invented indices.** Metrics align to
published operational criteria (Canadian FWI classes via EFFIS, NWS Red
Flag Warning conditions, WMO dry-day convention). No composite score is
synthesized. Rationale: borrowed, citable thresholds are defensible and
comparable; a bespoke index would be neither, and synthesis is precisely
where opacity enters risk products.

**Descriptive boundary.** Outputs are observed trends, historical rates,
recency percentiles, and event records — never predictions. Statements
about trend continuation are attributed to published climate literature.
Rationale: the project's authority derives from auditability; a forecast
would require validated skill the system does not claim, and the open
serving layer is intended as the substrate on which forecasting efforts
can be built transparently.

**Graceful degradation as a design property.** Layers fail independently:
if the FWI source is unavailable, percentile machinery rebuilds on vapor
pressure deficit and is relabeled; if a map layer underperforms, it is
dropped without affecting analytics or chat; if the live weather call
fails, the most recent available day is reported with its date. Every
degradation path is specified in docs/DATA.md (Part B) and tested in
docs/TESTING.md.

**Autonomous build orchestration.** The system is built by Claude Fable 5
against this repository's documents as the brief, with completion defined
machine-verifiably: the test tiers in docs/TESTING.md, acceptance
criteria in CLAUDE.md, and RUBRIC.md as the gradeable rubric. Verifier
sub-agents in fresh contexts grade milestones before the builder may
proceed; humans intervene only on escalation. Rationale: long-horizon
autonomous work is most reliable when "done" is checkable without
judgment calls — a test suite, a responding URL, a rubric file — and the
same property makes the setup rerunnable on a new problem.

**Provenance and the build-day boundary (explicit disclosure).** The
data layer is prior work, prepared before the event and disclosed as
such: open-data acquisition, the Python aggregation pipeline (`prep/`),
the serving layer it produced, and this documentation. Built during the
event window by Claude Fable 5: the entire platform — API, agent,
report, frontend, map, tests wiring, deployment. Live pipeline re-runs
during the event are explicitly out of scope — a deliberate limitation
that concentrates the build window on the platform. Reproducibility is
demonstrated instead by the committed pipeline code, the gate suite that
any reviewer can re-run against the data (`pytest -m "tier1 or tier2"`),
and the kickoff verification in which a verifier agent re-grades the
prior asset against RUBRIC R1 as the session log's first entry.

## Known blockers and contingencies

| Blocker | Impact | Contingency |
|---|---|---|
| EWDS queue latency or request-schema mismatch (FWI source) | delays the percentile features | Open-Meteo derivation path for daily variables; GEE Community Catalog mirror of the CEMS dataset; VPD-based percentile fallback |
| Downloaded FRAP release lacks the January 2025 fires | reference-event validation cannot run | NIFC/WFIGS open perimeters as the named substitute source |
| Anthropic API access (key, credits, rate limits) | chat layer unavailable | cached responses for the five reference ZIPs; map and analytics stand alone |
| Container host cold starts / free-tier sleep (Render) | dead demo moment | paid instance for event week (~$7) or keep-alive ping; warm-up visit pre-demo; `uvicorn --reload` local run is identical |
| Public API abuse on launch day | service degradation | read-only endpoints, parameter validation, modest rate limit middleware; worst case = API throttles while frontend caches |
| Event window (6.5 h build, 17:00 sharp submission incl. 1-min video) | unfinished layers | pre-committed cut lines; report+agent prioritized over map layers; video recorded at 16:30 regardless of polish state |
| Event credits ($500, day-of link, 24 h expiry) | build stalls on billing | personal funded key as immediate fallback; credits claimed at check-in before the brief |
| First-contact calibrations (grid registration, field names, units) | silent mis-joins if skipped | tracer-bullet protocol and Tier 1 gates in docs/TESTING.md; cell_id always derived from file coordinates |

## Repository layout
See CLAUDE.md (Repository map) for the authoritative file-by-file layout
and engineering conventions; docs/ARCHITECTURE.md (Part 2) for environment and
deployment mechanics.


---

## Appendix — Decision Ledger (settled questions; do not relitigate)
Every entry below was deliberated and closed during design. An
implementing agent that finds itself arguing against one of these is
drifting: raise DECISION CHALLENGE instead of proceeding.

**Identity & boundary**
- L1. FireLens is the open, auditable EVIDENCE layer beneath closed risk
  scores ("Fire Factor is the credit score; FireLens is the credit
  report"). It is descriptive: trajectory, record, present context.
- L2. NEVER: forecasts, burn probability, expected loss (AAL/eNVC),
  fire-behavior or spread claims, parcel/structure assessment, composite
  or invented indices, insurance/legal/transaction advice.
- L3. The industry's atomic metric (expected annual loss = hazard ×
  exposure × vulnerability) is deliberately NOT computed; FireLens
  publishes the evidence those models consume. FEMA NRI is the one open
  EAL instance — presentation context only.
- L4. Not RAG: no corpus, no embeddings, no similarity retrieval. Typed,
  parameterized SQL tools over a computed analytics layer. Agent tools =
  the public API endpoints; every report figure links to a replayable URL.
- L5. Primary surface = analyst + generated Fire Weather Report at `/`;
  map = supporting view at /explore, never the landing surface, always
  cuttable; the agent is never cut. The word "dashboard" appears nowhere.

**Event rules (binding)**
- L6. Streamlit banned; dashboard-as-main-feature banned; repo public;
  demo shows only event-built code; 10:30–17:00 window; 1-min video in
  the 17:00 submission; scoring Impact 35 / Demo 35 / Autonomy 15 /
  Orchestration 15.
- L7. Provenance boundary (disclosed in README): data, prep pipeline,
  docs = prior work; the entire platform (API, agent, report, map,
  deploy) = event-built by Claude Fable 5. Live pipeline re-runs during
  the event: out of scope. Commit history is the receipt.

**Stack (final, post-pivot)**
- L8. Python end-to-end: FastAPI + DuckDB in one Render container; static
  vanilla-JS + MapLibre frontend; agent loop server-side; build model
  claude-fable-5 (fallback claude-sonnet-4-6). No JS frameworks, no
  client-side DB. Key in env vars only, never shell-exported.
- L9. Zero-geometry rule: all spatial work happens once in prep
  (hub-and-spoke: aggregate-up / inherit-down / area-weighted
  apportionment / bounded snapping; fine→coarse only; fuel never
  multiplied into weather). Runtime = key lookups + scalar arithmetic.
- L10. Streaming: SSE tool-call progress events in; token streaming
  polish-only; live feeds/bulk endpoints = roadmap.

**Data (hard-won, several at 1 AM against a live system)**
- L11. GEFF fire indices come from EWDS, not CDS (one ECMWF login, two
  stores, separate licenses/endpoints). Dataset cems-fire-historical-v1
  v4.1, Global Land, 0.25° interpolated (only NetCDF path), Consolidated.
- L12. Request cost cap = 3,720 rows (vars × years × months × days) and a
  per-user submission throttle exist. Phase 1 (critical path, banked):
  FWI + ERC + DC, 3-year blocks, newest-first. Phase 2 (OPTIONAL, zero
  dependency): remaining components via serial cdsapi loop, ISI+BUI first.
- L13. Area box N 42.25 / W −124.5 / E −114 / S 32 — grid-aligned,
  typed never drawn; the box CONTAINS California, the TIGER polygon join
  DEFINES it. cell_id always derived from each file's own coordinates
  (F1 — the v4.1 grid was rebuilt and differs from prior versions).
- L14. Acquired ≠ served: the **v1 served set** (fwi, vpd, dry_wind_days,
  cdd, season_length) is fixed for launch but NOT a closed enum — the
  **Metric Extension Protocol** (registry in prep/metrics.py) admits further
  descriptive, non-composite metrics via one formula fn + one registry entry,
  with generic machinery (LUT/aggregate/trend/export/live) iterating the
  registry. ERC served on event cards; DC and all other components are
  archive-only until promoted through the protocol. Behavior indices
  (BI/IC/SC) never surface in claims; composite/invented indices stay banned.
- L15. Dailies come from Open-Meteo, not the CDS queue (decision locked
  after first-contact friction). Live "today" uses the FORECAST endpoint
  with past_days (the archive endpoint lags days — G12); wind requested
  in m/s; America/Los_Angeles dates.
- L16. Occurrence dedup F2: FPA-FOD statistics 1992–2020, FRAP 2021+;
  FRAP displays all eras. ≥300 ac statistics, ≥1,000 ac display. FRAP
  must contain PALISADES + EATON 2025 (NIFC is the named substitute).
- L17. Impact = per-fire aggregates only (Top 20 structures_destroyed,
  cause_class passthrough); fatalities excluded; never parcel-level.
- L18. Fuel (LANDFIRE FBFM40) = context layer: nearest-neighbor + zonal
  stats in EPSG:5070, composition + burnable_frac, never a join unit.
  Terrain/DEM deliberately absent (drives spread, which we don't model).
- L19. No-FWI degradation: percentile machinery rebuilds on VPD_max,
  relabeled; the anchor test degrades to VPD + Red Flag. Features never
  silently die.
- L20. Record-depth: baseline 1980–2000 is sacred; 1979+ truncation is
  pre-authorized (one number-sweep); pre-1979 = depth + headline.

**Process**
- L21. Tests-first and tests-locked; RUBRIC.md write-locked; verifier
  sub-agents grade milestones (fresh context); predict-then-run; every
  gate test must be shown to fail on injected bad data; golden snapshots
  of the five reference ZIPs after gates pass.
- L22. Pre-event sessions are developer-gated and plain-spoken (Session
  modes in CLAUDE.md); autonomous mode is the event window only. Cut
  ladder: overlays → entire map → reduced tools; the report/agent core
  is never cut. Definition of done is always machine-checkable.


---

# PART 2 — Development and deployment

> **Reading order:** 7 of 7 · **Depends on:** ARCHITECTURE.md (two-tier design it implements); DATA.md (Part C) (manifest contract); TESTING.md (gates wired into the workflow)
> **Single source of truth for:** environment setup, the two-root data layout, credential handling, git conventions, the build–verify loop, deployment mechanics
> **Forward references:** none

## Environment
- Python 3.11+ in one project venv for everything: pipeline, API,
  agent, tests. Node.js is needed only for Claude Code and mapshaper.
- Install:
  ```
  pip install duckdb geopandas shapely pyogrio pyarrow pandas requests \
      xarray netcdf4 anthropic cdsapi pytest rasterio rasterstats \
      fastapi "uvicorn[standard]" jinja2 httpx
  # optional, only if a Google Earth Engine fallback path activates:
  # pip install earthengine-api
  ```
  Pin with `pip freeze > requirements.txt`. Geospatial wheels bundle
  their native libraries — no system GDAL is required. The frontend is
  static HTML/CSS/JS with MapLibre GL from a CDN — no build step, no
  package.json for the app.
- Environment is frozen during release windows: no package, OS, or tool
  upgrades once a milestone is green.

## Two-root data layout
```
<repo>/                 code + serving layer (data/ ≤100 MB) — deployable
$FIRELENS_DATA/         raw/ interim/ exports/ — local only, never in git
```
All pipeline paths resolve through the `FIRELENS_DATA` environment
variable; no absolute paths in code. The only write path into the repo's
`data/` is `prep/07_export.py`, which runs the Tier 1–3 gates,
enforces the size budget, and writes `data/manifest.json`. Raw downloads
are immutable; interim products are regenerable; defects are fixed by
rerunning scripts, never by editing outputs.

`.gitignore` must cover: `.venv/`, `__pycache__/`, `.env`, `*.nc`,
`*.gdb`, `*.zip`, `scratch/`.

## Credentials
One home per secret; none in the repository (the repo is public):
EWDS and CDS API keys in their client configs (note: the GEFF dataset is
served from EWDS, not CDS — two stores, two configs); `ANTHROPIC_API_KEY`
in `.env` locally (gitignored, loaded at startup) and in the Render
service's environment variables. Only `app/agent.py` reads it; it never
reaches the frontend and is never exported in the shell (so Claude Code
stays on its subscription login). A key that reaches a commit is rotated
immediately.

## Git conventions
`main` is the deploy branch and receives only green commits (acceptance
criterion + relevant test tier passing). Small, atomic commits naming the
module and its proof (e.g., `lib/db.py: trends query <1s, tier4 green`).
Tag stable checkpoints. Experimental work goes on branches so `main`
stays releasable. Back up `$FIRELENS_DATA/interim/` once after the
pipeline completes; the serving layer is already version-controlled.

## Build–verify loop
One module per session: plan (and approve) → implement → run the module
and its test tier → inspect real output locally
(`uvicorn app.main:app --reload` hot-reloads; /docs shows the live API)
→ commit, push, verify the deployed URL → continue.
Failures get one bounded fix attempt (~30 minutes) before invoking the
pre-approved scope reductions in CLAUDE.md. In autonomous operation the
loop is run by the builder agent itself; milestones are graded by a
verifier sub-agent against RUBRIC.md before work proceeds, and the human
is consulted only at the escalation triggers (docs/TESTING.md, Part 3).

## Deployment
Render deploys from the public GitHub repository on every push to
`main`: it detects the Python app, installs `requirements.txt`, and runs
`uvicorn app.main:app --host 0.0.0.0 --port $PORT` — no Dockerfile
required (add one later for portability). The repo ships `data/` inside
the deploy, so DuckDB reads Parquet from local disk. Use a paid instance
(~$7) for the event week to avoid free-tier sleep, or a keep-alive ping.
Railway is the drop-in fallback host (same repo, same start command).
The Render log is the production log. `uvicorn --reload` locally is
functionally identical (same code, same data, key from `.env`) and is
the standing fallback during a demonstration. Note: ERA5-family timestamps
are UTC while users are in America/Los_Angeles; all stored joins use
calendar dates, and the live path converts to local date explicitly.
