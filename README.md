# FireLens 🔥🗺️

**The open record beneath the fire-risk scores.** FireLens is a
Claude-powered analyst that investigates any California ZIP code and
produces an evidence-cited Fire Weather Report: how the fire-weather
environment has actually changed across 85 years of atmospheric history,
which documented fires occurred nearby and the conditions on their
ignition days, and how today ranks against the full record — every number
retrieved from an auditable open dataset, with an interactive map for
exploration.

> 🚧 **Status: data layer complete; platform builds at the event.** The
> open-data pipeline and the <100 MB serving layer are built and
> validated (this repo). The app — API, agent, report, map — is built
> during Claude Fable Build Day, San Francisco, **June 13, 2026**. This
> README is the front door; **`docs/STATE.md` is the resume-point** for
> anyone (human or agent) picking the work up.

## Why
California's July 2025 disclosure expansion and the January 2025 Los
Angeles fires made fire risk a first-class question in every transaction —
and every accessible answer is a sealed score. Fire Factor is the credit
score; **FireLens is the credit report**: trajectory, not forecast; open
data, not a black box; free, for the people the enterprise tools skip.

## What it answers
- How fast Red Flag-condition days, atmospheric dryness, and the
  fire-weather season have grown at your ZIP since the 1980s — from a
  1940–present record.
- Which documented fires happened nearby, and how extreme the fire
  weather was on the day each ignited (e.g., Tubbs 2017 ignited on a
  **96th-percentile** fire-weather day for its location).
- How today ranks against everything that location has ever experienced.
- Where fuel can actually carry fire (LANDFIRE context), and how the
  federal hazard×exposure picture decomposes alongside the trend.

What it deliberately does **not** do: forecast, model fire spread, assess
parcels or structures, or give insurance/legal/transaction advice. The
serving layer is designed as open training and benchmark infrastructure
for community forecasting models — prediction is the ecosystem's layer,
built on top of this one.

## Architecture (no backend, on purpose)
Open data → local prep pipeline → a <100 MB Parquet serving layer queried
in-process by DuckDB inside one FastAPI service → a public REST query
API + a static MapLibre frontend + a Claude tool-use agent whose five
tools ARE the five public endpoints — every figure in a report links to a
URL anyone can replay, and the agent's tools are parameterized SQL (it
cannot assert a number it didn't retrieve). The deployed app performs zero
spatial computation; all geometry is resolved to keys at build time. Full
contracts: `docs/ARCHITECTURE.md`, `docs/DATA.md`, `docs/CONSUMER_BINDING.md`,
`docs/TESTING.md`.

## The serving layer (what's in this repo)
`data/` is the complete, self-contained serving layer — 11 committed
files, **5.6 MB**, the contract in `data/manifest.json`:

| layer | tables | grain | state |
|---|---|---|---|
| weather spine | `annual_metrics`, `pctile_lut`, `zip_trends` | 0.25° cell (824) → ZIP (1,801) | **served** |
| fire occurrence | `fire_events` | point → cell (556) | **served** |
| geography | `cell_meta`, `zip_meta`, `zip_cell_map` | keys | **served** |
| federal contrast | `nri_zip`, `zip_priority_matrix` | ZIP (1,693) | **additive** |
| fuel context | `fuel_context` | ZIP (1,801), 30 m raster underneath | **additive** |

**Served metric set (v1):** `fwi`, `season_length`, `dc_pctile` (era
trends per ZIP) + `fire_events` (ignition-day percentiles).
**Pending (blocked on the ERA5 daily harvest / build-day GEE backfill):**
`vpd`, `cdd`, `dry_wind_days`, `firms_density`. Pending metrics fold in
via idempotent re-export with **zero consumer code change** — the manifest
declares each metric's state and grain, and consumers read that contract
(`docs/SCHEMA.md`, `docs/CONSUMER_BINDING.md`).

**Honest NULLs (never fabricated):** 108 ZIPs absent from NRI's 1,693
(non-residential / not in HUD) carry NULL, not zero; 34 ZIPs with no
burnable fuel carry NULL composition, distinct from a real `burnable_frac=0`.
Three columns are 100% NULL by provenance — `structures_destroyed`,
`erc_pctile`, `zip_trends.robust` — and stay that way until honestly
sourced (see `docs/STATE.md` §5 and `docs/META_VALIDATION.md`).

## Reproduce
```bash
git clone <repo> && cd firelens
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# build the read-only DuckDB serving DB from the committed parquet
python prep/build_duckdb.py          # writes firelens.duckdb (gitignored)

# run the gates (98 pass; 7 are dailies, RED-by-design until the harvest lands)
pytest -q
```
The DuckDB is a **generated artifact** — the committed `data/` parquet is
the source of truth, and `build_duckdb.py` rebuilds an identical DB from it
(no dependency on the heavy data root). A diff-validation gate
(`tests/prep/test_duckdb_build.py`) asserts the DB equals source on row
counts, dtypes, NULL positions, value ranges, and ZIP-key format.

The full prep pipeline (`prep/0N_*.py` in order) regenerates `data/` from
raw open data and requires the heavy data root (`$FIRELENS_DATA`, outside
the repo) — see `docs/DATA.md`. Rebuilding the serving DB does **not**.

## Data & attribution
ERA5 / GEFF fire danger indices: Copernicus Climate Change Service & CEMS
(CC-BY 4.0) — "Contains modified Copernicus Climate Change Service and
CEMS information, 2026." Live conditions: Open-Meteo (CC-BY 4.0). Fire
records: USDA Forest Service FPA-FOD, CAL FIRE FRAP, NASA FIRMS (public
domain; FRAP is the most complete record available and still incomplete —
per its steward, and we agree). Geography: US Census TIGER; exposure: FEMA
National Risk Index; fuel: LANDFIRE (public domain).

## Honest limits
Atmospheric metrics are ~31 km resolution — the scale fire weather is
physically coherent at; this describes the environment around a location,
never a parcel. Fire–weather pairing covers 1992–present (vetted dates);
trends use the full 1940–present record. The federal NRI/matrix panel is a
2025 snapshot and an orthogonal *contrast* (consequence vs hazard), never a
validation of the trend. Methodology, validation histogram, and the
complete limitations list ship in-app.

## Provenance
Prepared **before Build Day (2026-06-12) and disclosed as prior work**: the
open-data acquisition, the Python aggregation pipeline (`prep/`), the
serving layer it produced (`data/`), the validation/meta-validation gates,
and this documentation. Built **during the event (2026-06-13) by Claude
Fable 5** from that brief: the platform itself — the public API, the
analyst agent, the Fire Weather Report, the map, the deployment. **The
commit history is the boundary, on purpose** — timestamps corroborate it.
Forward plan: `docs/DEVELOPMENT_PLAN.md`.

## License
Code: OSI license to be added before first release (MIT intended).
Data: per-source licenses above.

*Not affiliated with CAL FIRE, Copernicus/ECMWF, First Street, FEMA, or any
listed data provider. Not insurance, legal, or financial advice.*
