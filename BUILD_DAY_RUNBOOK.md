# BUILD_DAY_RUNBOOK.md — cold-start re-entry sequence

The literal steps to re-orient from a cold start (fresh clone or fresh CLI) and begin the
event build. Everything here works from **committed files alone** — no reliance on the
developer's memory or any prior session. Read top to bottom.

> **First principle:** the data layer is DONE and disclosed as prior work; today (2026-06-13)
> builds the **app** over it. The boundary is the commit history — do not squash/backdate, do
> not edit pre-event commits. Primary deliverable = the analyst + Fire Weather Report; the map
> is cuttable, the agent is not.

## 0. Orient (read, in this order)
1. `README.md` — what this is + the provenance boundary.
2. `docs/STATE.md` — **the resume-point.** §1 (re-verify the snapshot), §5 (next actions +
   the pending DECISIONS c-a..c-e), and the "If you read nothing else" line.
3. `docs/DEVELOPMENT_PLAN.md` — fixed core vs. flexible, the build-day sequence, pending decisions.
4. `CLAUDE.md` — operating mode, locked architecture, the canonical claim shapes.

## 1. Environment
```bash
cd ~/claudebuild/firelens
python -m venv .venv && source .venv/bin/activate    # or: source .venv/bin/activate if it exists
pip install -r requirements.txt
```
`$FIRELENS_DATA` (the heavy data root, outside the repo) is needed ONLY to re-run the full
prep pipeline. It is **NOT** needed to build the app or the serving DB — those read committed
`data/`.

## 2. Rebuild the serving DB (REQUIRED — it is gitignored, so it will NOT exist on a fresh start)
```bash
python prep/build_duckdb.py          # writes firelens.duckdb from committed data/ (read-only artifact)
```
Expect: `built firelens.duckdb` + `DIFF-VALIDATION vs source parquet: CLEAN (0 drifts)` and the
all-NULL list (`structures_destroyed`, `erc_pctile`, `zip_trends.robust`). If the diff is not
clean, STOP — the parquet/DB contract is broken; do not build on it.

## 3. Verify green before building
```bash
pytest -q                            # expect 98 passed / 7 dailies-pending (the 7 are RED-by-design)
python prep/validate.py              # join-resolution sweep: 7/7 PASS
python prep/verify_ca_footprint.py   # geographic footprint: real California (see check 6 spot-ZIPs)
```
The 7 `test_dailies` failures are EXPECTED (the ERA5 daily harvest is deferred post-event,
local-only). Everything else must be green. If anything else is red, fix before building.

## 4. Launch the agent and resume
```bash
export ANTHROPIC_API_KEY=...         # from the developer's environment / .env (gitignored), never committed
claude                               # then paste the resume prompt below
```
**Resume prompt:** "Read README.md, docs/STATE.md, and docs/DEVELOPMENT_PLAN.md. The data
layer is complete and validated (HEAD). Begin the build-day sequence in DEVELOPMENT_PLAN.md
Part 2: app skeleton over the DuckDB + manifest, the five endpoints = the five agent tools,
the agent loop (docs/AGENT.md), the Fire Weather Report. Respect the fixed contract (Part 1)
and the pending decisions (STATE.md §5, honest-or-drop). Build only in app/; do not touch the
data layer."

## 5. Build-day order (from DEVELOPMENT_PLAN.md Part 2 — summary)
1. App skeleton; validate `manifest.json` at startup (fail loud).
2. Five public endpoints = five agent tools (parameterized SQL over DuckDB).
3. Agent loop (`claude-fable-5`, fallback `claude-sonnet-4-6`, max 5 rounds, SSE progress).
4. The Fire Weather Report (every figure links to its API URL).
5. CONSUMER_BINDING spec → implementation (read `metric_domains`; NULL ≠ 0).
6. The non-blocky map (`/explore`): cell field + ZIP boundaries + event points + bivariate.
7. GEE/CDS backfill = the raw-weather DATA task (parallel; promotes pending→served by re-export).

## Guardrails (do not break — full list in DEVELOPMENT_PLAN.md Part 4)
- Served metric set + never-list (no forecasts/spread/parcel/composite scores).
- Grains + no false precision (no sub-cell interpolation, no parcel claims).
- DuckDB is generated (source = parquet; rebuild, never hand-edit; binary gitignored).
- NRI = contrast not validation; matrix = categorical quadrant, never a blended score.
- Claim-without-data columns (structures/erc/robust) — honest-or-drop, NEVER fabricate.
- Dailies/Lane-A stays local-only this event; the deployed app never depends on it.
- Breaking a fixed item is a DECISION CHALLENGE (cite the doc), not a quiet workaround.
