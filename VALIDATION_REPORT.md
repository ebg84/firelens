# VALIDATION_REPORT.md — spatial+temporal join-resolution sweep (AUTO-GENERATED)

Regenerate: `python prep/validate.py`. Gated by `tests/prep/test_validation_sweep.py`.
Result: **7/7 checks PASS**.

## PASS — 1. zip_cell_map both directions
- in_ca_cells(cell_meta): 824
- zip_serving_cells(zip_cell_map): 732
- canonical_ZCTAs: 1801
- ZCTAs_with_a_cell: 1801
- ORPHAN_ZIPs(no cell): 0
- weights_!=1.0: 0
- mapped_cells_missing_annual: 0
- NOTE_orphan_cells(in-CA, no ZCTA): 92
- note: ACCEPTED (2026-06-13): the 92 are in-CA cells beyond any ZCTA (sparse/border) — expected in-CA-buffer superset slack, NOT a hole. Load-bearing direction (0 orphan ZIPs, all 1,801 served, weights 1.0) is clean. Not tightened (harmless slack; tightening would touch the committed Module 7 export).

## PASS — 2. metric spatial universe
- zip_trends: {'n': 1801, 'outside_canonical': 0, 'gap_from_canonical': 0}
- nri_zip: {'n': 1693, 'outside_canonical': 0, 'gap_from_canonical': 108}
- zip_priority_matrix: {'n': 1693, 'outside_canonical': 0, 'gap_from_canonical': 108}
- fuel_context: {'n': 1801, 'outside_canonical': 0, 'gap_from_canonical': 0}
- annual_metrics: {'n': 824, 'cells_outside_cell_meta': 0}
- pctile_lut: {'n': 824, 'cells_outside_cell_meta': 0}
- nri_108_gap_ok: True
- fuel_zero_burnable_ZIPs: 12

## PASS — 3. cross-metric ZIP key alignment
- zip_trends: {'wrong_len(!=5)': 0, 'outside_canonical': 0}
- zip_cell_map: {'wrong_len(!=5)': 0, 'outside_canonical': 0}
- nri_zip: {'wrong_len(!=5)': 0, 'outside_canonical': 0}
- zip_priority_matrix: {'wrong_len(!=5)': 0, 'outside_canonical': 0}
- fuel_context: {'wrong_len(!=5)': 0, 'outside_canonical': 0}

## PASS — 4. temporal fields within declared range
- spine(fwi/erc/dc): {'range': [1940, 2026], 'ok': True}
- fire_events: {'range': [1992, 2025], 'ok': True}
- annual_metrics: {'range': [1940, 2026], 'ok': True}

## PASS — 5. granularity honesty (no finer-than-declared)
- annual_metrics_is_annual: True
- zip_trends_no_time_axis: True
- nri_zip_snapshot_no_time: True
- zip_priority_matrix_snapshot_no_time: True
- fuel_context_snapshot_no_time: True

## PASS — 6. no cross-domain join leakage (data level)
- cross_domain_tables: ['priority_matrix (fwi recent-level x NRI 2025, cross-sectional)']
- priority_matrix_no_time_dim: True

## PASS — 7. denorm regenerable
- status: N/A — no denormalized serving table built yet (gate ready: when built, it must rebuild-and-diff to the normalized source)

