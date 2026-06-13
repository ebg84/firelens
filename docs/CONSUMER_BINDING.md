# CONSUMER_BINDING.md — analytics/GIS binding spec (Part 3: SPEC now, BUILD on build day)

The data layer declares a per-metric coherence contract in `data/manifest.json`
(`metric_domains`, generated from `prep/domains.py`; human view in `docs/SCHEMA.md`).
This doc is the **rule the consumers must obey** and the **build-day fragility list** —
the spots a naive consumer would assume grain/range/granularity instead of reading the
contract. It is NOT implemented tonight; it is the directive for build day.

## The binding rule
**Every map/analytics surface reads `metric_domains` per metric and refuses or omits
out-of-domain requests.** No hardcoded metric lists, grains, or ranges. A
`pending -> served` promotion in the manifest must **auto-enable** the consumer with
**zero code change** (the consumer iterates the contract; a pending metric renders a
defined "data pending — blocked on {blocked_on}" state, never a broken layer or zeros).

## Build-day fragility list (each = a naive assumption -> the correct binding)
1. **Snapshot on a time axis.** `nri` / `priority_matrix` are `temporal_granularity:
   static` (2025 snapshot). NAIVE: plot/animate over years. BIND: read granularity; no
   time axis for static metrics.
2. **Continuous line from an era comparison.** `zip_trends` is two points
   (baseline vs recent). NAIVE: draw a trend line. BIND: the continuous annual series
   lives in `annual_metrics` (cell-grained) — read it there, or show 2 points honestly.
3. **Implied daily where only annual exists.** Served metrics are `era`/`annual`/`static`.
   NAIVE: a daily slider. BIND: refuse finer-than-declared `temporal_granularity` (daily
   only exists once vpd/cdd land).
4. **Metric shown for a ZIP that lacks it.** `nri`/`matrix` are `ZIP(1693)` — 108 ZCTAs
   (104 non-residential + 4 F8) have no value. NAIVE: blank/zero fill. BIND: omit-with-note
   for ZIPs absent from the metric's set.
5. **Cell↔ZIP mapped directly.** `fwi`/`season_length`/`dc_pctile` are
   `cell(824)->ZIP via zip_cell_map`. NAIVE: paint a cell value onto a ZIP (or vice versa).
   BIND: aggregate through `zip_cell_map` (weights) at query time.
6. **NRI×FWI framed as temporal.** It is a CROSS-SECTIONAL correlation across ZIPs.
   NAIVE: "fire weather over time vs NRI." BIND: label cross-sectional; never a time series.
7. **Point events as ZIP density.** `fire_events` is `point->cell(556)`. NAIVE: imply a
   ZIP-level fire count. BIND: render as points/perimeters; pairing is to cells, not ZIPs.
8. **Undeclared pending layer breaks the UI.** `firms_density`/`fuel_context` are declared
   `pending`. NAIVE: a hardcoded toggle that errors when the file is absent. BIND: render
   the pending state from the contract; auto-enable on promotion.

## GIS/UX rendering directive (build-day implementation; logged here now)
**Do NOT render flat, blocky ZIP-code choropleth fills** — that reads low-dimensional and
undersells the data. **Render each metric at its TRUE native grain (per the contract),
layered for depth:**
- **Continuous cell field** — the native 0.25° grid (824 cells) as a smooth field
  *beneath* ZIP boundaries, for visual depth and to show the atmosphere's real texture.
- **ZIP boundaries** — the digestible click-to-read number (the ZIP-aggregated value via
  `zip_cell_map`), overlaid on the cell field.
- **Event points / perimeters** — `fire_events` (point->cell) as overlays for texture.
- **Bivariate encoding** — e.g. hazard color × exposure saturation from `priority_matrix`,
  to show multidimensionality (the two axes at once) rather than one flat scalar.

**HARD CONSTRAINT — no false precision (the auditability thesis):** use ONLY the real
finer grains we actually computed (cells, fire points). **NEVER interpolate below the
0.25° cell resolution, and NEVER imply parcel-level detail we do not have.** A smooth
cell field is honest (it's the real grid); smoothing *below* a cell, or rendering a
parcel-scale value, fabricates precision and violates the thesis. The methodology line
("31 km atmospheric resolution; ZIP polygons display 31 km data") governs every render.
