# Data — Sources, Analytics, and Model

> **Reading order:** 2 of 5 · **Depends on:** ARCHITECTURE.md (hub-and-spoke resolution model, blocker register)
> **Single source of truth for:** the ENTIRE data layer — source universe and access (Part A), metric formulas and the serving DDL (Part B), field contracts, joins J1–J12, and failures F1–F10 (Part C)
> **Forward references:** TESTING.md (which gates every contract here)

---

# PART A — Data sources, access, and acquisition

> **Reading order:** 2 of 7 · **Depends on:** ARCHITECTURE.md (hub-and-spoke resolution model; blocker register)
> **Single source of truth for:** the data universe, per-source roles, granularity matrix, deliberate exclusions, access mechanics and verification labels
> **Forward references:** DATA.md (Part C) failure IDs F1–F10 and join IDs J1–J12; TESTING.md Tier 0.5 (tracer) and Tier 1 (acquisition gates)
What every dataset is, what role it plays, how they connect, at what
granularity each metric can honestly operate, and whether the whole is
sufficient for the mission: "the people's wildfire analysis and informatics
tool." Companion to DATA.md (Part B) (formulas) and DATA.md (Part A) (access notes below)
(access mechanics).

---

## 0. The organizing frame

Wildfire risk decomposes as **WEATHER × FUEL × IGNITION/OCCURRENCE ×
EXPOSURE**. Every dataset below plays exactly one primary role in that
decomposition, plus two service roles: GEOGRAPHY (how data gets aggregated
to human places) and LIVE (the present moment). A dataset that doesn't map
to one of these six roles doesn't belong in the layer.

FireLens's claim structure, restated as data requirements:
- "How has the fire-weather environment here changed?" → WEATHER, deep
  record, daily resolution.
- "Which real fires happened here, under what conditions?" → OCCURRENCE
  joined to WEATHER on (place, day).
- "Can fire even carry here?" → FUEL, static context.
- "What does the state already designate?" → EXPOSURE/regulatory reference.
- "What about right now?" → LIVE, ranked against the historical record.

---

## 1. Tier A — the committed universe (ten sources)

| # | Dataset | Role | Native res. (space / time) | Record | What FireLens extracts |
|---|---|---|---|---|---|
| 1 | **GEFF-ERA5 FWI** (Copernicus CEMS, via EWDS) | WEATHER | ~0.25° (~31 km) / daily | 1940–present | FWI; weekly percentile LUTs; season length; event-day percentiles |
| 2 | **ERA5 daily surface vars** (CDS; Open-Meteo fallback) | WEATHER | ~0.25° / daily | 1940–present | T max/min, dewpoint, wind max, precip → VPD, RH_min, Red-Flag days, CDD |
| 3 | **gridMET** (Climatology Lab) | WEATHER (fine-scale event context) | ~4 km / daily | 1979–present | ERC, BI, fm100/fm1000 at ignition points, Sonoma + LA only |
| 4 | **FPA-FOD 6th ed.** (USDA RDS) | OCCURRENCE | point / daily | 1992–2020 | ignition lat/lon, discovery date, size, size class, cause |
| 5 | **FRAP perimeters** (CAL FIRE) | OCCURRENCE + map visual | polygon / daily (alarm date) | 1878–present (dates reliable ~1990s+) | perimeter geometry, alarm date, acres; 2021+ pairing; annual acres for validation |
| 6 | **NASA FIRMS** (MODIS + VIIRS) | OCCURRENCE (detection density) | 1 km / 375 m points / sub-daily | 2000– / 2012–present | detection counts per hex; share on high-percentile days; in/out-perimeter flag |
| 7 | **TIGER ZCTA + counties** (Census) | GEOGRAPHY | polygon / static (2024 vintage) | — | aggregation polygons; county FIPS; ZIP↔cell weights |
| 8 | **FHSZ zones** (CAL FIRE/OSFM, 2025 maps) | EXPOSURE (regulatory reference) | polygon / static | current designation | overlay + per-ZIP zone share; the disclosure-rule baseline FireLens contextualizes |
| 9 | **LANDFIRE FBFM40** (+EVT/EVC) — *prep-window stretch* | FUEL | 30 m / quasi-static (rolling ~2-yr updates) | current | burnable fraction per ZIP/cell; dominant fuel class → volatility character text |
| 10 | **Open-Meteo live** | LIVE | ~0.25° (ERA5-family) / daily, near-real-time | today | current conditions → percentile rank vs source #1's LUTs |
| 11 | **CAL FIRE Top 20 (destructive)** | OCCURRENCE impact attribute | per fire / static list | major fires | structures_destroyed per named fire — aggregate only, event cards |

License posture: 1–2 CC-BY 4.0 (attribute Copernicus/C3S/CEMS and
Open-Meteo on the methodology page); 3–9 US public domain. Nothing in the
layer carries a usage restriction incompatible with a free public tool.

---

## 2. Tier B — the known universe deliberately NOT in scope
Cognizance means knowing what the developer excluded and why. Each of these is real,
public, and would extend the tool — and each is excluded for a stated
reason. This table doubles as the project roadmap.

| Dataset | Would add | Why excluded now |
|---|---|---|
| MTBS burn severity (1984+, 30 m) | "how bad," not just "whether" | new analytic dimension; zero demo lift for the core claims |
| FEMA National Risk Index | open county-level wildfire Expected Annual Loss | the industry's atomic metric, open — cited in pitch as the layer FireLens evidences; too coarse/static to join |
| NIFC/WFIGS perimeters | current-year + interagency fires | adopted as the NAMED FALLBACK if FRAP lacks 2025; otherwise redundant with FRAP |
| Live conditions feed (SSE/webhooks: "alert on Red Flag days in my ZIP") | push, not pull — the substrate becomes a service | requires schedulers + subscriber state + ongoing ops; the most natural post-event extension, zero build-day value |
| FWI decomposition view (FFMC/DMC/DC/ISI/BUI panels: "why is today's FWI high?") | de-black-boxes the served composite | data already archived from acquisition; pure v1.1 frontend work; zero build-day scope |
| Terrain/elevation (USGS 3DEP DEM: slope, aspect) | the classically expected fire layer | deliberately absent: slope/aspect drive fire SPREAD, which FireLens does not model; FHSZ zoning already embeds terrain; adding a DEM without a spread model is decoration. Roadmap alongside any future behavior layer |
| CAL FIRE incidents / NIFC-IRWIN feeds | live active-fire status | real-time ops is a different product contract (alerts, uptime) |
| CAL FIRE DINS damage inspections | structures destroyed per fire | impact layer; pushes toward loss modeling — off-thesis |
| SILVIS WUI maps | wildland-urban interface exposure | exposure modeling beyond reference overlays; roadmap |
| Census ACS demographics | equity/vulnerability views for planners | valuable post-build window planner feature; not buyer-facing core |
| Census ACS housing units (B25001) per ZCTA | "N homes, X% in Very High zone" exposure line | one-column quick win, but competes with the fuel layer for the same the pipeline window slack — fuel wins; roadmap |
| CAL FIRE DINS (structure-level damage) | full damage records per structure | structure-level granularity is the parcel line we don't cross; per-fire aggregates (S11) capture the demonstration value |
| NWS Red Flag Warning archive (e.g. IEM) | validate our Red-Flag-day metric against issued warnings | excellent future validation study; not launch-critical |
| US Drought Monitor (weekly) | drought context | CDD already carries drought accumulation at daily resolution |
| MODIS NDVI / fuel greenness | live fuel state | fm100/fm1000 + CDD cover fuel dryness; greenness adds little for the claims made |
| SAWTI (Santa Ana Wind Threat Index) | SoCal wind-event forecast context | forward-looking product; conflicts with the no-forecast boundary |
| Lightning (NLDN) | natural-ignition climatology | commercial license — fails the open test |
| Parcel/assessor data | parcel-level anything | explicitly banned: parcel precision claims are off-limits |
| Insurance/DOI non-renewal data | market-pressure context | one cited statistic in the presentation, not a data layer |

---

## 3. The join fabric — how everything connects

Four keys connect the entire universe. Every dataset reaches every other
dataset through at least one of them:

1. **Space — `cell_id`** (the master spatial key): the 0.25° lattice,
   `cell_id = round(lat*4)*10000 + round((lon+360)*4)`, membership = cell
   box intersects buffered CA polygon. Everything snaps to it: ERA5/GEFF
   natively; gridMET 4-km values extracted at ignition points then *tagged*
   with the containing cell; FIRMS points binned to hex AND tagged with
   cell; LANDFIRE 30-m pixels zonally aggregated up to cell and ZCTA;
   FPA-FOD/FRAP geometries snapped by centroid/point.
2. **Time — `date`** (UTC-normalized calendar date) with two derived
   rollups: `iso_week` (percentile climatology; week 53→52) and `year`
   (trend aggregation). Sub-daily sources (FIRMS) collapse to date;
   static sources (TIGER, FHSZ, LANDFIRE) join with no time key.
3. **Event — `fire_id`**: mints identity for each fire from FPA-FOD (1992–
   2020) or FRAP (2021+); carried as a GeoJSON feature property on served
   perimeters so map clicks join back to `fire_events`.
4. **Admin — `zip` (ZCTA) and county FIPS**: the human-facing rollup,
   reached ONLY via `zip_cell_map` (area-weighted) — never by joining
   analytics directly to admin polygons.

**The spine is `(cell_id, date)`.** Weather lives natively on the spine;
occurrence joins to it by snapping (point→cell, event date→date); fuel and
regulatory layers are static attributes OF cells/ZIPs; the live call is one
more (cell, today) row evaluated against the LUTs. Every sentence the
product can utter is a walk along this spine: *trend* = spine aggregated by
year and compared across periods; *event card* = one spine row looked up by
a fire; *today* = one spine row fetched live; *fuel context* = a static
attribute appended to the place.

Connection order in the pipeline (dependency-true): geography first (cells,
ZCTA weights, FIPS) → weather onto the spine → percentile LUTs →
occurrence snapped to spine → fuel/regulatory zonal stats → trend and
density aggregates → serving layer.

---

## 4. Granularity matrix — what each metric can honestly claim

Governing principle: **serve every claim at the coarsest granularity that
fully supports it, and never display at a finer granularity than the
measurement.** ZIP polygons *display* 31-km atmospheric data; the
methodology page says so in one sentence.

| Metric / claim | Measured at (space/time) | Served at | Honest record | Floor of validity |
|---|---|---|---|---|
| FWI percentile (events, today) | 31 km / daily | exact day at ZIP's dominant cell | 1940–present | day, single cell — never sub-cell |
| FWI trend, season length | 31 km / daily→annual | ZIP & county, period comparison | 1940–present | annual; ≥20-yr periods |
| Red Flag-condition days | 31 km / daily→annual count | ZIP & county trend | 1940–present | annual counts; daily wind-max caveat noted |
| VPD trend | 31 km / daily→annual mean of max | ZIP & county trend | 1940–present | annual |
| Consecutive dry days | 31 km / daily runs | annual max per ZIP; freq. ratio of ≥30-day runs | 1940–present | run-level; cross-year runs honored |
| ERC/BI event context | 4 km / daily | per-fire card, Sonoma + LA only | 1979–present | event-day point extraction only |
| Fire event pairing | point / day | per-fire percentile | 1992–present (vetted) | ≥300-ac fires; discovery-date precision |
| FIRMS density | 375 m–1 km / sub-daily→all-time | hex/cell counts | 2000/2012–present | density, never "a fire happened at this address" |
| Burnable fraction / fuel class | 30 m / quasi-static | % and dominant class per ZIP | current LANDFIRE cycle | composition stats, never pixel claims |
| FHSZ status | parcel-scale polygons / static | zone share per ZIP + overlay | current designation | reference only — their model, not ours |
| Today's rank | 31 km / today (CA calendar date) | percentile vs (cell, week) LUT | live vs 85-yr LUT | one day, one cell |

Two structural mismatches, owned openly rather than hidden: (a) the
**resolution inversion** — fuel is measured 1,000× finer than weather; we
therefore aggregate fuel UP to weather's geography rather than pretending
weather DOWN to fuel's; (b) the **era seam** — trends use 1940–present,
pairing uses 1992–present, FIRMS 2012-dense; every output states its own
record depth so no claim borrows another's history.

---

## 5. Sufficiency audit — is this universe enough for the mission?

**Questions the layer fully answers** (each mapped to its sources):
how the fire-weather environment here has changed and how fast (1, 2);
how extreme any day — past or today — is against 85 years of local history
(1, 10); which documented fires occurred here and the atmospheric state on
their ignition days (4, 5, 6 × 1, 3); whether the local fire-weather season
is lengthening (1); whether fuel can even carry fire here and of what
character (9); what the state's regulatory designation is and whether the
trend agrees with it (8 vs 1–2); where satellite-detected fire activity
clusters (6). That set covers every sentence in the product spec, every
demo beat, and every headline output promised since the first document —
**the universe is sufficient for the stated mission.**

**Questions the layer deliberately cannot answer** (the boundary, named):
parcel-level risk or structure vulnerability (no parcel/building data — by
design); fire *spread* simulation (no behavior modeling — closed
competitors' territory and the open-forecasting roadmap's job); smoke and
health impacts; insurance pricing; real-time incident status; any future
prediction. Each refusal is a positioning asset, not a gap: the agent
states the boundary and points to what the layer CAN say.

**The two honest soft spots**, pre-armed for Q&A: (a) daily-max wind from
reanalysis under-resolves canyon-scale gust behavior — mitigated by the
Red-Flag threshold choice and disclosed; (b) FRAP incompleteness and
pre-1990s date quality — mitigated by the FPA-FOD backbone and the era-seam
disclosure. Neither threatens a served claim at its served granularity.

**Sufficiency verdict: complete for launch.** Ten sources, six roles, four
join keys, one spine. Tier B is cognizance, not debt — every exclusion has
a reason that survives a reviewer's "why not X?" The data layer needs no new
members before release day; it needs its downloads finished and its anchor test
green.


---

## Appendix — Access mechanics and verification status
Facts below are labeled [VERIFIED] (confirmed against a live source),
[TRAINING] (high-confidence, confirm on first use), or [ASSUMPTION]
(must be confirmed before reliance). First-contact items (request-key
spellings, grid registration, field names) are retired by the
tracer-bullet protocol in TESTING.md before bulk acquisition.

## Dataset facts

### GEFF-ERA5 fire danger indices (FWI source)
- [VERIFIED] Dataset: "Fire danger indices historical data from the Copernicus
  Emergency Management Service", ID `cems-fire-historical-v1`, current
  version 4.1. https://ewds.climate.copernicus.eu/datasets/cems-fire-historical-v1
- [VERIFIED] Computed by ECMWF's GEFF model from ERA5 forcing; Canadian FWI
  system plus US NFDRS and Australian indices; record extends as ERA5 does.
  Reference: Vitolo et al. 2020, Sci Data 7:216.
- [VERIFIED] v4.1 supports **area cropping** in the request (use it — CA bbox
  only), and NetCDF requests covering multiple dates return a ZIP.
- [VERIFIED] EWDS dataset page live. v4.1 release notes: NetCDF
  is constructed from GRIB via MIR interpolation and **the grid differs
  from previous versions** (hard confirmation of the F1 rule: derive
  cell_id from the file's own coordinates); units changed to SI. Request
  keys follow the `'variable': 'fire_weather_index'`,
  `'system_version': '4_1'` convention — confirm exact keys in the EWDS
  form's API snippet during the tracer bullet.
- [VERIFIED] **Queue-free FWI fallback discovered:** the CEMS
  fire daily 4.1 dataset is mirrored in the Google Earth Engine Community
  Catalog (`projects/climate-engine-pro/assets/ce-cems-fire-daily-4-1`).
  If the EWDS queue stalls, FWI is extractable per-cell via GEE — the
  "FWI absent entirely" risk drops from low-med to low.
- [TRAINING] Variable name for FWI in v4.x NetCDF: `fwinx` /
  "fire_weather_index"; grid ~0.25°. Confirm against the first downloaded file.
- [ASSUMPTION] Queue times on EWDS are shorter than legacy CDS but
  unpredictable; chunk requests by decade and queue all chunks at the start of the acquisition window.

**EWDS request specification (final — supersedes any prior variable list):**
- Product type: Reanalysis · Dataset type: Consolidated · Version: 4.1
- Variables: **Canadian FWI system group, Select all (7: BUI, DC, DMC,
  FFMC, DSR, FWI, ISI) + U.S. NFDRS group, Select all (4: BI, ERC, IC,
  SC). Australian group: none** (no consumer, eucalypt-calibrated).
  Rationale: acquisition generosity — the Canadian components exist
  nowhere else on the 1940+ spine and decompose the served composite;
  the NFDRS set completes the US-system archive for audit. **Serving
  stays FWI + ERC only (v1 served set); behavior-semantic indices (BI, IC,
  SC) never surface in product claims** — fire behavior is outside the
  descriptive boundary, same rule that excludes spread modeling.
- Area: **N 42.25 / W −124.5 / E −114 / S 32** — every edge a multiple
  of 0.25 so the store's grid-snap returns the identical extent on every
  request (typed, never map-drawn; enter once, leave untouched across
  all blocks). The box is a deliberate superset: "actual California" is
  resolved in the pipeline by J1 (cell ∩ TIGER boundaries → CA cell set,
  county, land_frac) — the request contains California; the polygon join
  defines it. Mixed-extent blocks from earlier bounds are harmless:
  cell_id derives from each file's own coordinates (F1), so blocks align
  on shared cells. · Grid: 0.25° × 0.25° interpolated · Format: NetCDF4
  (GRIB + cfgrib is the fallback)
- [VERIFIED at first contact] **Request-cost cap: 3,720 rows** (counted
  as variables × years × months × days; one year of all 11 variables =
  4,092 = already over). Chunking is therefore variable-split, two phases:
  **Phase 1 (critical path): FWI + ERC (+ Drought code riding along in
  3-year/3-variable blocks, 3,348 rows — DC adopted at acquisition as the
  one variable not captured by, nor reconstructible from, any other
  source: 52-day stateful deep-drought memory, and local FWI-system
  implementation is banned; acquired-not-served, enum unchanged)** — 2 × 5 × 372 =
  3,720 exactly; 18 web-form requests cover 1940–2026; these are the
  only variables the pipeline consumes. (Form rejects the boundary value
  → 4-year blocks, 22 requests.)
  **Phase 2 (OPTIONAL — the pipeline, serving layer, tests, and demo
  have ZERO dependency on it; skip or cancel without any consequence to
  project scope): remaining 9 components,
  per-year scripted requests — run ISI + BUI first (FWI's two direct
  parents; the decomposition view's first split), then the moisture
  codes, then the NFDRS remainder** — 9 × 372 = 3,348; 86 jobs via a cdsapi
  loop using the captured snippet; acquired-not-served, blocks nothing.
- Time: tracer = 2017 / October / all days, 11 variables × 31 = 341 rows
  (under cap, unaffected — contains the Tubbs anchor); multi-date NetCDF
  returns ZIPs (expected). ~2–4 GB total to $FIRELENS_DATA/raw/geff/ —
  never deploys.
- [VERIFIED at first contact] **Per-user submission throttle exists**:
  bulk hand-submission was rate-limited after ~13 blocks (reached 1988,
  2026→1988 banked incl. both anchors + full pairing era). Limits are
  temporary and reset within hours. Remaining priority: **three blocks
  (1985–87, 1982–84, 1979–81) complete the 1980–2000 baseline — first
  action of the next session**; pre-1979 = depth, via script, whenever.
  The serial cdsapi loop is inherently throttle-compliant (one job at a
  time).
- Procedure: accept CC-BY → fill → copy the completed "Show API request
  code" snippet verbatim (ground-truth schema) → submit tracer → submit
  all blocks in the same sitting (one-shot generosity rule),
  **newest-first priority order** (2024–26 backwards to 1940–42): per-user
  jobs process roughly in submission order, so anchors (2017, 2025), the
  pairing era (1992+), the baseline (1980–2000), and the satellite-era
  record (1979+) complete first; the 1940s–50s land last as depth +
  headline. **Pre-authorized degradation:** if early blocks are
  unfinished at the noon gate, ship with what's complete — a 1950+ start
  is scientifically defensible (ERA5 back-extension uncertainty) and
  costs exactly one docs sweep (85 → 75 years); baseline, trends,
  anchors, and percentiles are all unaffected.

### ERA5 daily variables
- Primary: CDS (standard https://cds.climate.copernicus.eu account + dataset
  license acceptance required before first API call). [TRAINING]
- [VERIFIED] Fallback with zero queue: **Open-Meteo Historical Weather API**,
  endpoint `/v1/archive` — ERA5 at 0.25° from **1940 to present** (ERA5-Land
  0.1° from 1950), daily aggregation parameters, JSON/CSV, multi-decade
  single-location responses typically <100 ms, multi-location batching
  supported. https://open-meteo.com/en/docs/historical-weather-api
- [VERIFIED at probe 2026-06-12] Bulk archive pulls MUST pass `models=era5`
  (join integrity, non-negotiable): it lands on the 0.25° ERA5 grid cell-center,
  an exact match to the GEFF cell (F1) — the default returns a ~0.1° offset point
  and `models=era5_land` returns null wind/precip. `dew_point_2m_mean` (the VPD
  humidity ingredient) and `temperature_2m_mean` are served daily aggregations;
  `wind_speed_unit=ms`; `timezone=GMT` (UTC daily, matches the spine, F7). Daily
  `wind_speed_10m_max` is sustained, not gusts: ERA5 0.25° under-resolves
  Diablo/Santa-Ana gust events (Tubbs day reads ~4.6 m/s sustained), so the
  Red-Flag-day metric undercounts wind-driven events — disclosed caveat (§6).
- [CITATION] Methodology-page attribution: Open-Meteo — Zippenfenig, P. (2023),
  *Open-Meteo.com Weather API*, Zenodo, doi:10.5281/zenodo.7970649 (CC-BY 4.0);
  ERA5 — Hersbach, H. et al. (2020), *The ERA5 global reanalysis*, QJRMS
  146:1999–2049, doi:10.1002/qj.3803. (GEFF/CEMS FWI cited via Vitolo et al. 2020.)
- [TRAINING — confirm at tracer] **G12 latency:** the /v1/archive
  endpoint serves reanalysis and lags real time by days (ERA5 latency);
  "today" must come from the **/v1/forecast endpoint with `past_days`**,
  which serves current conditions from weather models. The live feature
  reports "the most recent available day," date-labeled.
- [TRAINING] Daily parameter names to use: `temperature_2m_max`,
  `temperature_2m_min`, `dew_point_2m_mean`, `wind_speed_10m_max`,
  `precipitation_sum`. Confirm exact names against the live docs page when
  writing the puller (Open-Meteo guarantees no breaking renames, but check).

### FPA-FOD (fire-occurrence pairing backbone)
- [VERIFIED] Current: **6th edition, 1992–2020**, `RDS-2013-0009.6`,
  ~2.3M georeferenced wildfire records, each requiring discovery date, final
  size, and a point location to PLSS-section precision or better.
  https://www.fs.usda.gov/rds/archive/catalog/RDS-2013-0009.6
- [TRAINING] Ships as SQLite/GeoPackage among other formats; key fields:
  `DISCOVERY_DATE`, `LATITUDE`, `LONGITUDE`, `FIRE_SIZE`, `FIRE_SIZE_CLASS`,
  `NWCG_GENERAL_CAUSE`, `STATE`. Confirm field names on load.

### FRAP fire perimeters
- [VERIFIED] "California Fire Perimeters (all)" on California Open Data /
  CNRA hub, maintained annually by CAL FIRE FRAP, released each spring with
  the prior year's fires. Direct machine downloads exist, e.g. GeoJSON:
  `https://gis.data.cnra.ca.gov/api/download/v1/items/c3c10388e3b24cec8a954ba10458039d/geojson?layers=0`
  (GeoPackage/Shapefile/GDB variants on the same dataset page).
  https://data.ca.gov/dataset/california-fire-perimeters-all
- [VERIFIED] Steward's own caveat: most complete digital record but still
  incomplete; use caution for statistical claims (quote this on the
  methodology page — it shows rigor).
- [TRAINING] Key fields: `YEAR_`, `FIRE_NAME`, `ALARM_DATE`, `CONT_DATE`,
  `GIS_ACRES`, `AGENCY`, `CAUSE`. Confirm on load.

### NASA FIRMS
- [TRAINING] Archive download via https://firms.modaps.eosdis.nasa.gov/download/
  — requires free NASA Earthdata login; request CA, MODIS (2000+) + VIIRS
  (2012+); CSV delivered by email link, usually within hours. Submit at the start of the acquisition window.
- [TRAINING] Confidence fields differ: MODIS 0–100 numeric; VIIRS
  nominal/low/high categorical. Filter MODIS ≥ 30 and VIIRS != 'l' for the
  density layer.

### CAL FIRE Top 20 lists (adopted micro-addition)
- [TRAINING] CAL FIRE publishes official Top 20 Most Destructive /
  Largest / Deadliest California wildfire lists (fire.ca.gov, updated
  after major incidents); per-fire structures-destroyed totals are on the
  Destructive list. 20 rows, public domain, hand-keyed with source URL;
  verify totals at entry. Fatalities not used in the build.

### GEFF page verifications (live, from the dataset Overview at acquisition)
- [VERIFIED] Horizontal coverage **Global Land** — California in scope;
  ocean cells in the bbox are NaN by design (Tier 1 asserts values over
  land; ocean NaN expected, not a defect).
- [VERIFIED] **Energy release component present** in the catalogue,
  units **J/m²** (v4.1 SI conversion) — irrelevant to FireLens claims,
  which are percentiles; record the unit in the manifest.
- [VERIFIED] NetCDF exists for **interpolated grids only** — the 0.25°
  interpolated + NetCDF4 combination is the only NetCDF path, validating
  the locked choice. Original Gaussian grid is GRIB2-only.
- [VERIFIED] Years through 2026; daily updates; CC-BY accept button on
  the form; API snippet live-updates with selections (copy it once
  complete — it is the ground-truth request schema).

### NIFC / WFIGS perimeters (named fallback only)
- [TRAINING] National Interagency Fire Center open-data hub publishes
  interagency fire perimeters including current/recent years — the named
  fallback if the downloaded FRAP release lacks the 2025 LA fires. Public
  domain.

### FEMA National Risk Index (pitch context only — NOT in the build)
- [TRAINING] FEMA NRI publishes open, county/tract-level wildfire Expected
  Annual Loss estimates — the one open instance of the industry's atomic
  metric. Use: a single cited line in the presentation/Q&A ("even FEMA's open EAL
  is county-coarse and static; FireLens supplies the daily, local,
  85-year evidence layer beneath numbers like that") and a Tier B roadmap
  row. Zero build hours.

### Census TIGER + FHSZ
- [TRAINING] ZCTAs: TIGER/Line 2024 vintage, national ZCTA5 file from
  census.gov, filter to CA (~1,700–1,800 ZCTAs); counties from the same
  program. Public domain.
- [TRAINING] FHSZ: CAL FIRE / Office of the State Fire Marshal published
  updated maps in 2025; download via the OSFM/FRAP GIS hub. Confirm the developer have
  the post-2025 LRA+SRA version, since that's what the disclosure rules key
  off.

### gridMET (reference counties only)
- [TRAINING] GEE ImageCollection `IDAHO_EPSCOR/GRIDMET`, daily CONUS ~4 km,
  1979–present; bands include `erc`, `bi`, `rmax`, `rmin`, `vs`, `pr`.
  Alternative: Climatology Lab THREDDS/direct NetCDF.
- LOCKED: point extraction at Sonoma + LA ignition locations only.

### LANDFIRE FBFM40 (fuel context — prep-window stretch)
- [TRAINING] USGS/USFS LANDFIRE program; current LF 2023/2024 cycle; 30 m
  GeoTIFF in CONUS Albers (EPSG:5070); CA clip via the LANDFIRE download
  app at landfire.gov (a few hundred MB). Non-burnable codes 91/92/93/98/99;
  burnable classes GR/GS/SH/TU/TL/SB (101-204). Public domain.
- Handling rules locked in DATA.md (Part B) 4.6 and DATA.md Part C F10:
  nearest-neighbor resampling only; zonal stats in EPSG:5070; never
  multiplied into weather metrics.

## Platform facts

### Hosting (Render; prior notes superseded)
- [VERIFIED] 1 GB memory guaranteed per app; exceeding it shows an error page
  and emails the developer; apps sleep when not accessed; deploys from a
  public GitHub repo. https://docs.streamlit.io/knowledge-base/deploy/resource-limits
- Implication: serving layer + simplified GeoJSON target ≤100 MB on disk,
  lazy-load ZIP geometries per county, warm the app before the demonstration.

### Anthropic API (for the in-app agent)
- [VERIFIED — Anthropic product info] Current API models include
  `claude-sonnet-4-6` (recommended for the FireLens agent loop: fast,
  cheap, strong tool use) and `claude-opus-4-8`; `claude-fable-5` is the
  newest flagship. Showcase the Messages API tool-use loop — it's a Claude
  Build Day. Current request shape and rate limits:
  https://docs.claude.com/en/api/overview
- [ASSUMPTION] The event may provide API credits — check the event page /
  event channels before the build window; affects nothing architecturally.

## Open assumptions to retire on first contact with data
1. GEFF v4.1 grid registration and FWI variable name (check first NetCDF).
2. FPA-FOD and FRAP field names as listed (check on load; trivial to adapt).
3. Open-Meteo daily parameter spellings (check docs page when writing puller).
4. EWDS queue behavior (observed during acquisition; the Open-Meteo path is the hedge).
5. Event rules on pre-built code vs pre-acquired data (confirm before the build window).


---

# PART B — Analytics: formulas, thresholds, and the serving DDL

> **Reading order:** 3 of 7 · **Depends on:** DATA.md (Part A) (which sources supply which variables)
> **Single source of truth for:** all metric formulas and thresholds (with citations), the v1 served metric set and the Metric Extension Protocol (§4.5/§4.5a), the serving-layer DDL (single schema source of truth), aggregation and degradation contracts, the limitations appendix
> **Forward references:** DATA.md (Part C) calibrations F1 (cell_id from file coordinates) and F2 (occurrence dedup), defined in the next document
Every formula cites the standard it implements. Judgment calls are marked
CHOICE with a one-line justification. This file is the contract between the
prep pipeline and the app — if a number on screen can't be traced to a rule
here, it's a bug.

## 1. Derived daily metrics (per ERA5 cell, per day)

### 1.0 The atomic spatial unit: `cell_id`
The 0.25° lattice: `cell_id = round(lat*4)*10000 + round((lon+360)*4)`;
membership = the cell box intersects the TIGER California polygon buffered
10 km. **Calibration rule (DATA.md (Part C) F1):** the lattice registration is
derived from the FIRST downloaded GEFF NetCDF's actual lat/lon arrays —
never assumed — and Open-Meteo pulls must use those same centers. Each cell
stores `land_frac`; cells <30% land are kept for percentile math but
excluded from choropleth weighting.

### 1.1 Saturation vapor pressure, RH, VPD
Magnus formula, Alduchov & Eskridge (1996) coefficients (WMO-endorsed):

    es(T)  = 6.1094 * exp(17.625*T / (T + 243.04))      # hPa, T in °C
    ea     = es(Td)                                      # Td = dewpoint °C
    RH     = 100 * ea / es(T)                            # clip to [0, 100]
    VPD    = (es(T) - ea) / 10                           # kPa, floor at 0

Daily values: VPD_max from (T_max, Td_mean); RH_min approximated from
(T_max, Td_mean). CHOICE: this approximation slightly overstates RH_min when
dewpoint dips intraday — conservative in the safe direction (undercounts
Red-Flag days, never inflates the headline).

### 1.2 Red Flag-condition day (the "dry-wind day")
CHOICE — statewide operationalization of NWS Red Flag Warning criteria
(which vary by NWS office, RH thresholds ~15–25%):

    red_flag_day = (wind_speed_10m_max >= 11.18 m/s)     # 25 mph sustained
                   AND (RH_min <= 25)

Justification: 25 mph/25% is the most common criterion family; a single
statewide rule keeps trends comparable across ZIPs. Display label:
"Red Flag-condition days." Sensitivity variant at RH ≤ 15% computed once and
reported on the methodology page.
**UNITS GUARD:** all wind is stored in m/s. Open-Meteo returns km/h by
default — request `wind_speed_unit=ms` or convert at ingest; Tier 2 asserts
statewide plausibility (a 3.6× error flips every Red Flag count).

### 1.3 Consecutive dry days (CDD)
    dry_day = precipitation_sum < 1.0 mm                  # WMO dry-day convention
Runs accumulate across calendar-year boundaries (a Nov–Feb drought is one
run). Annual statistic `cdd_max` = longest run *ending* in that year.
Implementation: DuckDB window — `SUM(CASE WHEN NOT dry THEN 1 ELSE 0 END)
OVER (PARTITION BY cell_id ORDER BY date)` as run-group key, then group.

### 1.4 Fire-weather day & season length
    fire_weather_day = FWI >= 21.3
CHOICE: 21.3 is the EFFIS "high" class lower bound (EFFIS classes: 5.2 /
11.2 / 21.3 / 38.0 / 50.0). `season_length(year)` = count of fire-weather
days. Report the FWI ≥ 38 ("extreme") count as a secondary statistic.
**FWI scale is open-ended** — the Canadian FWI has no upper bound, and GEFF
documents it as such. The served corpus (1940–2026) ranges 0 → ~238.5, the
maximum occurring in arid Great Basin/Mojave cells in late spring–summer under
high Drought Code (verified geographically/seasonally coherent at ingest, F1
tracer). Raw values are never clamped or rescaled; acquisition and spine gates
assert `fwi ≥ 0` with a `< 500` sanity ceiling whose only job is to catch a
unit-error slip (a km/h-style 3.6× or order-of-magnitude error), never a real
extreme.

### 1.5 Weekly FWI percentile rank
- Bin by ISO week; ISO week 53 merged into week 52 (avoids a thin bin).
- LUT: per (cell, week), `quantile_cont(fwi, [0.5, 0.8, 0.9, 0.95, 0.99])`
  over ALL years 1940–2025.
- A day's percentile = `percent_rank()` of its FWI within its (cell, week)
  population. By construction ~uniform over all days — which is exactly what
  makes the validation histogram (§4) meaningful.

## 2. Trend statistics (baseline 1980–2000 vs recent 2010–present)
Per ZIP (area-weighted over member cells) and per county, per metric:
- `pct_change` of period means (Red Flag days/yr, VPD_max mean, season length).
- `freq_ratio` for rare events (CDD runs ≥ 30 days; FWI ≥ p95 days):
  recent rate / baseline rate.
- Robustness flag (CHOICE — cheapest defensible): bootstrap the 21 baseline
  years (1,000 resamples) → 90% CI of the baseline mean; `robust = recent
  mean outside CI`. The UI shows it as a footnote dot; reviewers can ask.

## 3. Fire–weather pairing
- Sources: FPA-FOD 6th ed (1992–2020, `DISCOVERY_DATE`), FRAP (2021–present,
  `ALARM_DATE`; earliest in-perimeter FIRMS detection refines location).
- **Dedup rule (DATA.md (Part C) F2):** the two sources overlap 1992–2020;
  fire *statistics* take FPA-FOD exclusively for 1992–2020 and FRAP
  exclusively for 2021+. FRAP geometries still display for all eras —
  display ≠ statistics. Tier 3 checks event-count plausibility across the
  2020/2021 seam.
- Snap: ignition point → nearest ERA5 cell centroid (≤ ~22 km by
  construction; fine at 31 km physics).
- Assign: that (cell, ISO week) percentile of that date's FWI; plus gridMET
  ERC percentile for Sonoma + LA county fires only.
- Filters: statistics use fires ≥ 300 acres (FPA-FOD size class E+);
  the map displays perimeters ≥ 1,000 acres.

## 4. Validation histogram (the credibility artifact)
- Population A: ignition-day FWI percentiles, all paired fires ≥ 300 acres.
- Population B: the uniform reference (all days ≈ flat by construction).
- Plot: share of ignitions per decile, with the 10% uniform line drawn.
- The claim it must support: "X% of large-fire ignition days rank above the
  80th percentile of local historical fire weather, vs 20% expected by
  chance." Computed once in prep; shown on the methodology tab; exposed to
  the agent via get_methodology_stats.

## 4.5 Served metric set & ZIP-level aggregation
The **v1 served set**, used verbatim by pipeline, tools, and UI:
`fwi`, `vpd`, `dry_wind_days`, `cdd`, `season_length`. No synonyms anywhere.
This set is fixed for launch but **not a closed enum** — see §4.5a.

### 4.5a Metric Extension Protocol (the served set is extensible, not closed)
The served set is a **registry** (`prep/metrics.py`), not a hardcoded enum. Each
metric is one `Metric` record — `name, unit, tier, served, inputs, daily_fn,
annual_fn, percentile, trend_kind, degradation, live_fn, formula_ref,
claim_shape` — and the generic machinery (derived-daily → annual_metrics →
pctile_lut → zip_trends → export, plus the live "today" path) iterates the
registry **in an explicit fixed order, never naming a metric**. Adding a metric
= one formula function + one registry entry; no LUT/trend/export/live edit (the
dummy-propagation test in 05_aggregates proves this). A metric enters the served
set (`served=True`) only after it clears the full chain: a Tier-2 formula test,
a stated `claim_shape`, and a docs line.
**Hard limits — the protocol is descriptive-only:** every metric must trace to a
published formula/standard and be a *single* measure; there is no path to
combine metrics. Forecasts, fire-behavior/spread characterizations, parcel-level
claims, and composite/invented indices remain banned (never-list). `degradation`
names the per-metric fallback when a source is dark (e.g. `fwi → vpd_substitute`,
`season_length → its relabeled variant`, dailies metrics → `None`); `live_fn`
defines how the metric ranks a single live forecast-day (Friday's live module
reuses it rather than reimplementing). Candidates staged `served=False` pending a
named gate after Module 05: `dc_pctile` (deep-drought percentile, data already on
the spine) and an ERC-based annual metric (ERC already on event cards).
ZIP-level annual series (sparkline) are NOT a stored table: computed at
query time as the `zip_cell_map`-weighted average over `annual_metrics`
(milliseconds in DuckDB). Map joins use county FIPS, never county names.
The "today" tool evaluates a ZIP's **max-weight cell**. get_fires_near
computes great-circle distance from zip_meta centroid to fire_events
lat/lon as SQL arithmetic (haversine) — pure math on columns, so the
zero-geometry rule stays intact; results are labeled "approximate distance
to fire center." 
Second-pass granularity contracts (G-series):
- **G5 county aggregation:** county_trends = land_frac-weighted mean over
  the county's member cells (mirrors the ZIP rule; never an average of ZIPs).
- **G7 ZCTA↔county:** ZCTAs cross county lines; each ZIP is assigned its
  majority-area county for drill-down and zip_meta.county_fips. A
  border ZIP appears under one county only — documented, not a bug.
- **G4 missing-metric degradation:** if the FWI path fails, fwi/
  season_length rows are simply absent from zip_trends; tools return
  "metric unavailable for this location" rather than erroring, and the
  agent says which metrics it does have. **Crucially, pctile_lut is then
  built on VPD_max instead of FWI** (VPD is an accepted primary fire-danger
  metric in the literature), so event cards, the live "today" rank, and
  the validation histogram all survive FWI loss — relabeled "VPD
  percentile" everywhere they render. The percentile machinery never goes
  dark; only its index changes, and the label says so.
- **Acquired-not-served (decomposition archive):** the full Canadian
  component set (FFMC, DMC, DC, ISI, BUI, DSR) is downloaded and archived
  in $FIRELENS_DATA alongside FWI, because no other source carries it on
  the 1940+ spine. It is NOT aggregated, NOT in the serving layer, NOT in
  the enum — it exists so every served FWI value is verifiable down to
  its published ingredients (Van Wagner 1987), and to feed a future
  decomposition view. The methodology page explains how FWI is built
  from these components, in plain language, with citations — the
  industry-standard composite is the product; its open construction is
  the proof.
- **ERC sourcing (closes the erc_pctile gap):** Energy Release Component
  is pulled from the same EWDS dataset (NFDRS group) alongside FWI;
  erc_pctile is computed with the identical (cell, week) percent_rank
  machinery. If the form's NFDRS group lacks it, erc_pctile ships NULL
  and event cards omit the line — degradation, not failure.
- **Impact aggregates rule:** structures_destroyed is a historical fact
  about a named fire — same epistemic class as acreage. Rendered on event
  cards when present; NEVER per-structure, never apportioned to ZIPs,
  never extrapolated toward any property. Fatalities deliberately
  excluded from the build. Source: CAL FIRE Top 20 Most Destructive list,
  hand-keyed with source URL, numbers verified at entry.
- **G9 pre-1992 fire cards:** perimeters older than the pairing era show
  name/year/acres from GeoJSON properties with the line "atmospheric
  pairing available for fires since 1992." Never a blank card, never a
  fabricated percentile.

## 4.6 Fuel context (LANDFIRE FBFM40 — prep-window stretch)
Per ZIP and cell: class composition, `burnable_frac` (share of pixels in
burnable classes; non-burnable codes 91 urban / 92 snow-ice / 93
agriculture / 98 water / 99 barren), and `dominant_class` mapped to
descriptive character text (grass: ignites easily, moves fast ·
grass-shrub · shrub/chaparral: intense, ember-heavy · timber-understory /
timber-litter: severe, persistent · slash). Rules: zonal statistics in
EPSG:5070; nearest-neighbor resampling only; categoricals aggregate by
mode/composition, never mean; fuel is context and visual underlay — it is
**never multiplied into weather metrics** and no composite index exists.
ZIPs with `burnable_frac` < ~0.15 are masked/hatched in the choropleth and
the agent names the fuel context unprompted.

## 5. Serving-layer DDL (DuckDB)
```sql
CREATE TABLE cell_meta    (cell_id INT PRIMARY KEY, lat DOUBLE, lon DOUBLE,
                           county_fips VARCHAR, land_frac DOUBLE);
CREATE TABLE zip_meta     (zip VARCHAR PRIMARY KEY, lat DOUBLE, lon DOUBLE,
                           county_fips VARCHAR);  -- ZCTA centroid: powers
                           -- fires-near distance + map centering (D1)
CREATE TABLE zip_cell_map (zip VARCHAR, cell_id INT, weight DOUBLE);
CREATE TABLE annual_metrics (cell_id INT, year INT, fwi_mean DOUBLE,
  fwi_max DOUBLE, vpd_max_mean DOUBLE, red_flag_days INT, cdd_max INT,
  season_len INT, extreme_days INT);
CREATE TABLE pctile_lut   (cell_id INT, iso_week INT,
  p10 DOUBLE, p20 DOUBLE, p30 DOUBLE, p40 DOUBLE, p50 DOUBLE, p60 DOUBLE,
  p70 DOUBLE, p80 DOUBLE, p90 DOUBLE, p95 DOUBLE, p99 DOUBLE);
  -- deciles + tails (D3): today's value brackets to a tight band
CREATE TABLE zip_trends   (zip VARCHAR, metric VARCHAR, baseline DOUBLE,
  recent DOUBLE, pct_change DOUBLE, freq_ratio DOUBLE, robust BOOLEAN);
CREATE TABLE county_trends(county_fips VARCHAR, county VARCHAR,
  metric VARCHAR, baseline DOUBLE, recent DOUBLE, pct_change DOUBLE,
  freq_ratio DOUBLE, robust BOOLEAN);   -- FIPS is the join key (D2)
CREATE TABLE fire_events  (fire_id VARCHAR PRIMARY KEY, name VARCHAR,
  ign_date DATE, acres DOUBLE, lat DOUBLE, lon DOUBLE, cell_id INT,
  county_fips VARCHAR, fwi_pctile DOUBLE, erc_pctile DOUBLE,
  structures_destroyed INT,  -- nullable; CAL FIRE Top 20 list, per-fire
                             -- aggregate ONLY (never structure-level)
  cause_class VARCHAR,       -- nullable; FPA-FOD cause passthrough
                             -- (e.g. Lightning / Human); display only
  source VARCHAR);  -- lat/lon (D1): centroid retained for app-side
                    -- haversine; distances labeled "≈ to fire center"
CREATE TABLE firms_density(hex_id VARCHAR, lat DOUBLE, lon DOUBLE,
  n_detections INT, share_high_pctile DOUBLE,
  frp_mean DOUBLE, frp_max DOUBLE);  -- FRP = intensity proxy, free column
CREATE TABLE fuel_context (zip VARCHAR PRIMARY KEY, burnable_frac DOUBLE,
  dominant_class VARCHAR, class_json VARCHAR);  -- stretch; absent = layer off
```

## 6. Limitations appendix (methodology page, verbatim)
- ERA5 resolves the atmosphere at ~31 km: this describes fire *weather* around
  a location, not conditions at a specific parcel.
- Trend metrics describe atmospheric drivers, not vegetation, ignition
  sources, or structure vulnerability.
- FRAP is the most complete perimeter record available and still incomplete
  (per CAL FIRE FRAP's own use guidance); pre-1990s dates are less reliable,
  so event pairing uses 1992-present.
- FIRMS detects heat sources including prescribed and agricultural burns.
- Fuel context (where present) is LANDFIRE composition at its current
  mapping cycle: it shows where fire can carry, not how a fire would behave.
- FireLens describes observed trajectories; it does not forecast.
  Expectations of trend continuation belong to the published climate
  literature and are attributed to it.
- FireLens is not a catastrophe model and provides no insurance, legal, or
  transaction advice. Weather data: Open-Meteo / Copernicus C3S & CEMS
  (CC-BY 4.0); fire records: USDA FS, CAL FIRE, NASA (public domain).


---

# PART C — Data model: field contracts, join registry, failure registry

> **Reading order:** 4 of 7 · **Depends on:** DATA.md (Part B) (the DDL its joins operate over); DATA.md (Part A) (the sources its field contracts map)
> **Single source of truth for:** source→canonical field contracts, the join registry J1–J12, the failure registry F1–F10, the manifest contract, the zero-geometry doctrine
> **Forward references:** TESTING.md (which turns every F/J item into a gated assertion)
The contract for the data layer. Thesis up front: **the GIS layer stays
workable if and only if the app performs zero spatial computation.** Every
geometric question — which cell, which ZIP, which county, inside which
perimeter, what fuel composition — is answered once, in prep, and stored as
a plain foreign key or number. The deployed app does key lookups and GROUP
BYs. If that principle holds, the backend cannot be messy where it counts;
if it leaks, no amount of cleanup saves the map.

---

## 1. Why this backend works (the load-bearing arguments)

1. **Volume math closes.** Spine = ~700 cells × ~31,400 days ≈ 22M rows ×
   ~10 numeric columns ≈ 1–2 GB Parquet locally; DuckDB aggregates it in
   seconds. Serving layer ≈ 120k rows of aggregates + ~25–40 MB GeoJSON +
   optional fuel PNG — under the 100 MB repo budget and trivially under
   the API service's container memory budget.
2. **No moving parts in production.** DuckDB runs in-process over files
   committed in the repo: no DB server, no connection pool, no migrations,
   no auth, no network dependency for data. The only runtime failure
   surface is two outbound APIs, both with scripted fallbacks.
3. **Spatial complexity is quarantined in time.** GeoPandas/shapely/
   exactextract run only on the pipeline phase on the development machine. Critically, the deployed
   app needs NO spatial extension — a real risk eliminated, since
   extension installs at app boot are a network dependency the developer don't want.
4. **The pipeline is regenerable and gated.** raw/ immutable, interim/
   reproducible from scripts, serving layer written by exactly one script
   that refuses on red tests. Any discovered defect is fixed by rerunning,
   never by hand-editing outputs.

## 2. Where it breaks without iteration (the honest registry)
Ranked by (likelihood × damage). Each has an owner-step and a test.

| # | Failure mode | Why it happens | Mitigation / iteration point |
|---|---|---|---|
| F1 | **Grid registration mismatch** — GEFF cells offset half-a-cell from the assumed lattice, silently snapping everything to neighbors | 0.25° products differ in cell-center vs cell-edge registration | Tracer bullet: read actual lat/lon arrays from first NetCDF; derive `cell_id` FROM the file's coordinates, never from assumption. Assert Open-Meteo pulls use the same centers. THE #1 first-contact iteration |
| F2 | **Double-counted fires** — FRAP and FPA-FOD overlap 1992–2020; naive union inflates event counts and the validation histogram | two occurrence sources, same era | Dedup by era rule: fire_events takes FPA-FOD exclusively for 1992–2020, FRAP exclusively for 2021+. FRAP geometries still display for all eras (display ≠ statistics). Test: no fire_id duplicates; per-year event counts plausible across the 2020/2021 seam |
| F3 | **Field-name drift** — FPA-FOD 6th ed renamed cause fields vs 5th; FRAP field casing varies by export format | versioned datasets | Loader maps source→canonical names in ONE place (`prep/fields.py`); Tier 1 asserts canonical columns exist. Iteration expected on first load, trivial cost |
| F4 | **Coastal/ocean-blend cells** — half-ocean cells damp absolute FWI/wind | 31 km cells straddle coastline | Keep cells (percentile-vs-self cancels mean bias) but store `land_frac`; flag cells <30% land out of choropleth weighting. Test: coastal vs inland gradient check still passes |
| F5 | **GeoJSON property loss** — simplification drops `fire_id`/FIPS, breaking map-click joins | mapshaper/shapely defaults | Export checklist asserts required properties on every feature post-simplification. Test: random perimeter click resolves to a fire_events row |
| F6 | **Schema drift between prep and app** — app written against columns the pipeline renamed | two codebases, one contract | `data/manifest.json`: every table's schema, row count, build timestamp, git hash. `lib/db.py` validates manifest at startup and fails loudly with the diff |
| F7 | **Timezone seam** — UTC daily bins vs California calendar dates | ERA5 is UTC; fires are local | All joins on calendar DATE (documented approximation, negligible at daily/31 km); live path converts via America/Los_Angeles explicitly. Test: live call after 5pm PDT returns today, not tomorrow |
| F8 | **ZCTA ≠ ZIP** — postal ZIPs without ZCTA polygons (PO-box ZIPs) | Census abstraction | Input validation: unknown ZIP → nearest-ZCTA suggestion message, never a crash. Documented in methodology |
| F9 | **FRAP date nulls** (esp. pre-1990s) | source quality | Already designed around: trends never use fire dates; pairing uses FPA-FOD era + post-2000 FRAP where ALARM_DATE valid. Test: pairing-input null rate <5% |
| F10 | **Categorical raster resampled numerically** — invented fuel classes | wrong resampling default | Nearest-neighbor only; zonal stats in EPSG:5070. Test: output rasters contain only legal FBFM40 codes |

Verdict shape: nothing in F1–F10 is architectural; all are first-contact
calibrations with written tests. The design needs *iteration*, not
*rethinking* — and the iteration points are now enumerated, which is what
"rigorously tested on paper" means.

---

## 3. Source-by-source field contracts
Canonical names on the left of `←`; expected source names right (confirm on
first load per F3; alternates in parens).

**S1 GEFF-ERA5 FWI** (NetCDF, EWDS) — `fwi ← fwinx` (fire_weather_index);
coords `lat/lon/time`. Derive: `cell_id` from coordinate arrays (F1),
`date` from time (UTC). Keys out: (cell_id, date, fwi).

**S2 ERA5 dailies / Open-Meteo** — `t_max ← temperature_2m_max`,
`t_min ← temperature_2m_min`, `td_mean ← dew_point_2m_mean`,
`wind_max ← wind_speed_10m_max` (NOTE units: Open-Meteo km/h default —
request m/s or convert; classic F-series bug), `precip ← precipitation_sum`.
Keys out: (cell_id, date, 5 vars) → derived (rh_min, vpd_max,
red_flag, dry_day).

**S3 gridMET** (GEE `IDAHO_EPSCOR/GRIDMET`) — `erc`, `bi` (+`fm100`,
`fm1000` optional), sampled at ignition points. Keys out:
(fire_id, erc, erc_pctile, bi) for Sonoma+LA events only.

**S4 FPA-FOD 6th ed** (GeoPackage/SQLite) — `fire_id ← 'FOD-'||FOD_ID`,
`ign_date ← DISCOVERY_DATE`, `lat/lon ← LATITUDE/LONGITUDE`,
`acres ← FIRE_SIZE`, `size_class ← FIRE_SIZE_CLASS`,
`cause ← NWCG_GENERAL_CAUSE` (5th-ed alternate: STAT_CAUSE_DESCR),
filter `STATE='CA'`. Stats filter: size_class ≥ E (≥300 ac).

**S5 FRAP perimeters** (GeoPackage) — `fire_id ← 'FRAP-'||YEAR_||'-'||
slug(FIRE_NAME)`, `ign_date ← ALARM_DATE`, `acres ← GIS_ACRES`,
`name ← FIRE_NAME`, `agency ← AGENCY`, geometry. Roles split: display
(all eras, ≥1,000 ac, simplified, MUST carry fire_id property per F5) vs
statistics (2021+ only per F2).

**S6 FIRMS** (CSV) — `lat/lon ← latitude/longitude`, `date ← acq_date`,
`conf ← confidence` (MODIS numeric ≥30; VIIRS categorical ≠'l'),
`frp`, `instrument`. Keys out: hex_id (H3 ~res 6–7 or 0.05° bin), cell_id,
date, in_perimeter flag.

**S7 TIGER** — ZCTA: `zip ← ZCTA5CE20`, geometry; County: `fips ← GEOID`,
`county ← NAME`, filter `STATEFP='06'`. The admin geometry source of
truth — FRAP county fields are never trusted over a spatial assignment.

**S8 FHSZ** (OSFM 2025) — `haz_class ← (FHSZ / HAZ_CLASS — confirm on
load)`, geometry, LRA/SRA flag. Keys out: per-ZIP share by class +
simplified display layer.

**S9 LANDFIRE FBFM40** (GeoTIFF, EPSG:5070) — pixel codes: 91 urban,
92 snow/ice, 93 agriculture, 98 water, 99 barren (non-burnable);
101–109 GR grass, 121–124 GS grass-shrub, 141–149 SH shrub, 161–165 TU
timber-understory, 181–189 TL timber-litter, 201–204 SB slash. Keys out:
per-ZIP/cell class composition, `burnable_frac`, `dominant_class`; legend
PNG. Zonal stats in 5070; NN resampling only (F10).

**S10 Open-Meteo live** — same vars as S2 for today (America/Los_Angeles
date per F7) at the queried ZIP's max-weight cell centroid.

---

## 4. The join registry (every join, with cardinality and its test)

| J# | Join | Method | Cardinality | Validity test |
|---|---|---|---|---|
| J1 | lattice × CA polygon → cell membership | box-intersects buffered state | — → ~700 rows | count in [550, 900]; no cell >60 km from land |
| J2 | ZCTA × cells → zip_cell_map | area overlay in equal-area CRS | N:M with weights | every ZIP ≥1 cell; weights sum 1.0 ±1e-6 |
| J3 | cells → county | majority-area FIPS | N:1 | spot ZIPs/counties correct (95404→Sonoma, 90272→LA, 94588→Alameda) |
| J4 | S1 grid → cell_id | snap from file coords (F1) | 1:1 | round-trip lat/lon↔cell_id exact; S1 and S2 agree on centers |
| J5 | S1 + S2 → spine | key merge (cell_id, date) | 1:1 | post-1950 coverage ≥98% both sides; FWI present where vars present |
| J6 | S4 points → spine | nearest centroid + DISCOVERY_DATE | N:1 | synthetic centroid ignition returns exact cell/day; snap distance ≤22 km |
| J7 | S5 (2021+) → spine | centroid (refined by earliest in-perimeter S6 detection) + ALARM_DATE | N:1 | 2021+ majors present (e.g., Palisades, Eaton); F2 seam counts plausible |
| J8 | S6 → hex + cell + perimeter flag | point bin + point-in-polygon (prep only) | N:1 | hex totals = point totals; flagged share sane (0.2–0.9) |
| J9 | S9 → ZCTA/cell composition | exactextract zonal, EPSG:5070 | raster→N rows | fractions sum 1.0; Mojave ZIP burnable_frac low, Sierra timber ZIP high |
| J10 | S8 × ZCTA → zone share | area overlay | N:M | shares sum ≤1.0; VHFHSZ ZIPs nonzero where expected |
| J11 | S10 → pctile_lut | key (cell_id, iso_week) | 1:1 | rank in [0,1]; F7 evening test |
| J12 | map click → fire_events | GeoJSON `fire_id` property (F5) | 1:1 | random clicks resolve; zero orphan properties |

Reading the table is the proof of the thesis: **every spatial method lives
in J1–J10, all prep-side; the app touches only J11–J12, which are key
lookups.** That is the entire answer to "if the data layer is messy, the
GIS layer is impossible" — the GIS layer never sees the mess because it
never performs geometry.

---

## 5. The flawless-backend doctrine (seven rules)
1. **App does zero spatial computation.** All geometry resolved to keys in
   prep (J1–J10). No shapely, no geopandas, no spatial extension in
   requirements of the deployed app.
2. **Three zones, one legal crossing.** raw/ immutable → interim/
   regenerable → data/ written only by the gated export.
3. **One canonical name per concept**, mapped from sources in one file
   (`prep/fields.py`). Downstream code never sees a source spelling.
4. **The manifest is the contract** (F6): schemas, row counts, build hash
   in `data/manifest.json`; `lib/db.py` refuses to start on mismatch.
5. **Tests gate, never decorate**: export refuses on red Tier 1–3; modules
   are done at green acceptance, not at "code exists".
6. **Idempotent scripts**: every prep stage rerunnable from raw/ with
   identical output; fixes are reruns, never edits.
7. **Display ≠ statistics**: a dataset may serve both (FRAP), but each
   claim consumes the era/filter contracted for it (F2, F9), and every
   output states its own record depth.

## 6. Roadmap to flawless (and the final ruling)
Order is dependency-true and already encoded in the pipeline build sequence:
geography (J1–J3) → tracer-calibrated weather (F1, J4–J5) → metrics →
LUTs → pairing with dedup (F2, J6–J7) → density (J8) → fuel/regulatory
(J9–J10) → trends → gated export with manifest. Two iterations are
*scheduled*, not feared: grid registration (F1, ~30 min at tracer time)
and field-name calibration (F3, ~15 min per source at first load).

**Ruling: the design is valid as specified.** It would fail only if (a)
both weather paths fail (two independent providers — remote), (b) the
anchor test fails unfixably (the gate exists to catch it the pipeline window, not
release day), or (c) the app is allowed to do geometry (now forbidden in
writing). Everything else on the risk surface is a named, tested,
sub-hour calibration. This document closes the design phase: the backend
has no remaining unknowns that paper can resolve — only unknowns that a
NetCDF header resolves.


---

## 7. Validation addendum — the time of writing executed simulation
The full serving schema and join registry were executed in DuckDB with
synthetic data (14/14 checks green: cell_id round-trip over 1,806 lattice
cells, weights, weighted sparkline, LUT monotonicity + today-bracket, ISO
week-53 merge, cross-year CDD window SQL, F2 violation detection, haversine
fires-near, J12 fire_id resolution, metric enum, FIPS joins). Three schema
defects were caught and are now canon in DATA.md (Part B) §5:
- **D1 — fire/ZIP locations were missing.** get_fires_near had no
  coordinates to compute distance with. Fixed: fire_events gains lat/lon
  (centroid); new `zip_meta` table (ZCTA centroid + county_fips). Distance
  is SQL haversine — arithmetic, not geometry; zero-geometry rule intact —
  and is labeled "approximate distance to fire center."
- **D2 — county joins were keyed on names.** county_trends/cell_meta now
  carry county_fips as the join key (names retained for display only).
- **D3 — pctile_lut was too coarse for the live feature.** Five quantiles
  could only bracket "today" into wide bands; the LUT now stores deciles +
  p95/p99 (11 thresholds; ~37k rows regardless).
**Canonical serving tables (the manifest's table set):** cell_meta,
zip_meta, zip_cell_map, annual_metrics, pctile_lut, zip_trends,
county_trends, fire_events, firms_density, fuel_context (stretch) — plus
data/geo/*.geojson and data/manifest.json.