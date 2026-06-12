# FireLens 🔥🗺️

**The open record beneath the fire-risk scores.** FireLens is a
Claude-powered analyst that investigates any California ZIP code and
produces an evidence-cited Fire Weather Report: how the fire-weather
environment has actually changed across 85 years of atmospheric history,
which documented fires occurred nearby and the conditions on their
ignition days, and how today ranks against the full record — every number
retrieved from an auditable open dataset, with an interactive map for
exploration.

> 🚧 **Status: in development** — built for Claude Fable Build Day,
> San Francisco, June 13, 2026. This README describes the design; see
> `docs/` for the full specifications.

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
  weather was on the day each ignited (e.g., Tubbs 2017: ~97th percentile
  of 85 years at that location).
- How today ranks against everything that location has ever experienced.
- Where fuel can actually carry fire (LANDFIRE context), and what the
  state's hazard-zone designation says alongside the trend.

What it deliberately does **not** do: forecast, model fire spread, assess
parcels or structures, or give insurance/legal/transaction advice. The
serving layer is designed as open training and benchmark infrastructure
for community forecasting models — prediction is the ecosystem's layer,
built on top of this one.

## Architecture (no backend, on purpose)
Open data → local prep pipeline → a <100 MB Parquet serving layer queried
in-process by DuckDB inside one FastAPI service → a public REST query
API + a static MapLibre frontend + a Claude tool-use agent whose five
tools ARE the five public endpoints — every figure in a report links to
a URL anyone can replay
whose tools are parameterized SQL (it cannot assert a number it didn't
retrieve). The deployed app performs zero spatial computation; all
geometry is resolved to keys at build time. Full contracts:
`docs/ARCHITECTURE.md`, `docs/DATA.md (Part C)`, `docs/DATA.md (Part B)`, `docs/TESTING.md`.

## Data & attribution
ERA5 / GEFF fire danger indices: Copernicus Climate Change Service & CEMS
(CC-BY 4.0) — "Contains modified Copernicus Climate Change Service and
CEMS information, 2026." Live conditions: Open-Meteo (CC-BY 4.0). Fire
records: USDA Forest Service FPA-FOD, CAL FIRE FRAP, NASA FIRMS (public
domain; FRAP is the most complete record available and still incomplete —
per its steward, and we agree). Geography: US Census TIGER; hazard zones:
CAL FIRE/OSFM; fuel: LANDFIRE (public domain).

## Honest limits
Atmospheric metrics are ~31 km resolution — the scale fire weather is
physically coherent at; this describes the environment around a location,
never a parcel. Fire–weather pairing covers 1992–present (vetted dates);
trends use the full 1940–present record. Methodology, validation
histogram, and the complete limitations list ship in-app.

## Provenance
Prepared before Build Day and disclosed as prior work: the open-data
acquisition, the Python aggregation pipeline (`prep/`), the serving
layer it produced (`data/`), and this documentation. Built during the
event by Claude Fable 5 from that brief: the platform itself — the
public API, the analyst agent, the Fire Weather Report, the map, the
deployment. The commit history is the boundary, on purpose.

## License
Code: OSI license to be added before first release (MIT intended).
Data: per-source licenses above.

*Not affiliated with CAL FIRE, Copernicus/ECMWF, First Street, or any
listed data provider. Not insurance, legal, or financial advice.*
