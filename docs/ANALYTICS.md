# ANALYTICS.md — buildable-now vs pending (from the served layer + the manifest contract)

What the analytics/agent layer can compute TODAY off the served + additive data, vs what
PENDS on the harvest/wind. Each maps to the grain it renders at (per the coherence contract).
Ground truth as of `1c2ff49`.

## BUILDABLE NOW (served + additive data exists)
| analytic | data | grain it renders at | claim shape |
|---|---|---|---|
| **Era trend** (fwi / season_length / dc_pctile) | zip_trends | ZIP (cell-field underneath) | "+9.3% statewide fwi_mean; 98% of ZIPs rising; baseline vs recent" |
| **Ignition-percentile histogram** (the credibility artifact) | fire_events.fwi_pctile | point→cell | "X% of large-fire ignitions above the 80th pctile vs 20% by chance" |
| **Event card** | fire_events | per-fire | "Tubbs ignited 2017-10-08 on a **96.2nd-pctile** day" |
| **Recency percentile** | pctile_lut (cell×iso_week) | cell→ZIP (max-weight cell) | "the last N years rank in the Pth pctile of the local record" |
| **Hazard×exposure matrix** | zip_priority_matrix | ZIP | priority / monitor / harden / low_priority quadrants (438/408/408/439) |
| **NRI contrast / decomposition** | nri_zip + zip_trends | ZIP (1693) | the orthogonality exhibit (Death Valley vs Palisades); never spun as a correlation win |
| **Fuel composition** | fuel_context | ZIP (30 m raster underneath) | "P% burnable; dominant = shrub/chaparral" (Palisades reads SH=0.66) — burnable_frac primary |
| **Fires-near** | fire_events + zip_meta | point | haversine from ZCTA centroid (labeled "≈ to fire center") |
| **Comparison** | zip_trends across ZIPs | ZIP | "Red-Flag-condition trend grows X× faster in A than B" (fwi/season_length today) |

## PENDING (needs harvest / wind / raw measurements)
| analytic | needs | dependency / path |
|---|---|---|
| **VPD trend** | `vpd` | ERA5 t_max + td_mean → 05 rerun (harvest, or build-day GEE) |
| **Red-Flag-days trend** ("+43%" headline) | `dry_wind_days` | wind — NOT from CDS; **build-day GEE ERA5 u/v** → speed-max |
| **Dry-spell / CDD trend** | `cdd` | ERA5 precip → 05 rerun (harvest / GEE) |
| **Raw weather foregrounding** (temp/precip/wind) | raw dailies | none today (spine is indices); harvest / GEE |
| **FIRMS detection-density heat layer** | `firms_density` | NASA FIRMS (not staged) — additive |

## Notes for the analytics/GIS layer (per CONSUMER_BINDING.md)
- Read `metric_domains`; render each metric at its TRUE grain (cell field / ZIP boundaries /
  fire points), layered — never a flat ZIP choropleth, never finer than 0.25° (no false precision).
- NRI/matrix are a 2025 SNAPSHOT (no time axis); zip_trends is a 2-point ERA comparison (not a
  line); the continuous annual series lives in cell-grained annual_metrics.
- The mean-vs-tail fix (PENDING): switching the matrix hazard axis to high-percentile-day count
  unifies it with the Tubbs 0.962 headline and re-sorts the Tubbs city into `priority`.
