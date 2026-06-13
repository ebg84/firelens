"""Module 8a — FEMA NRI wildfire VALIDATION layer (table join, no raster).

The headline is test_intensive_uses_denominator: the corrected aggregation — intensive
fields (WFIR_RISKS, WFIR_AFREQ) are residential-weighted AVERAGES with an explicit
Σ(weight) denominator; the extensive field (WFIR_EALT, dollars) is a bare allocation.
NRI is a validation reference beside FireLens, never a served risk metric.
"""
import json

import pandas as pd

from prep import nri, paths

NRI_ZIP = paths.INTERIM / "nri_zip.parquet"
DIAG = paths.INTERIM / "nri_diagnostics.json"


# ---- aggregation math (oracle, runs now) -------------------------------------

def test_intensive_uses_denominator_extensive_does_not():
    # tract A (risks 80, afreq .04, ealt 100) and B (risks 40, afreq .02, ealt 200),
    # both contribute res_ratio 0.25 to ZIP Z -> ZIP weight-sum = 0.5 (rest is elsewhere),
    # so the denominator MATTERS: a bare sum would halve every intensive value.
    nri_df = pd.DataFrame({"tract": ["A", "B"], "wfir_risks": [80.0, 40.0],
                           "wfir_afreq": [0.04, 0.02], "wfir_ealt": [100.0, 200.0]})
    xw = pd.DataFrame({"tract": ["A", "B"], "zip": ["Z", "Z"], "res_ratio": [0.25, 0.25]})
    out = nri.aggregate_to_zip(nri_df, xw, {"Z"}).iloc[0]
    assert abs(out["wfir_risks"] - 60.0) < 1e-9    # (80*.25+40*.25)/0.5 = 60, NOT bare-sum 30
    assert abs(out["wfir_afreq"] - 0.03) < 1e-9
    assert abs(out["wfir_ealt"] - 75.0) < 1e-9     # 100*.25+200*.25 = 75 (extensive allocation)


# ---- gate (red until prep/08_nri_validation.py runs) -------------------------

def _require():
    assert NRI_ZIP.exists() and DIAG.exists(), "run prep/08_nri_validation.py first"


def test_crosswalk_integrity():
    """Σ RES_RATIO per residential tract ~ 1.0 (zero-residential tracts excluded)."""
    _require()
    d = json.load(open(DIAG))
    assert d["crosswalk"]["max_dev_from_1"] < 0.01, d["crosswalk"]


def test_no_unexplained_coverage_gaps():
    """The real gate (not a fitted threshold): EVERY unmatched ZCTA must be explained —
    either non-residential (res_ratio=0 under our residential weighting) or absent from
    HUD entirely (F8). Zero may be 'recoverable' (res_ratio>0 yet dropped) — that would
    be a join bug. Verified root cause: 104 non-residential + 4 F8, 0 bugs."""
    _require()
    c = json.load(open(DIAG))["coverage"]
    assert c["unmatched_recoverable_bug"] == 0, f"unexplained/recoverable gaps: {c}"
    assert c["unmatched_total"] == c["unmatched_non_residential"] + c["unmatched_f8_absent"], c
    assert c["served_zips_matched_frac"] >= 0.90, c  # sanity floor only; cause is the gate


def test_every_zip_has_a_contributing_tract():
    _require()
    import duckdb
    n = duckdb.connect().execute(f"select count(*) from '{NRI_ZIP}' where n_tracts < 1").fetchone()[0]
    assert n == 0


def test_wfir_ranges_sane():
    _require()
    import duckdb
    r = duckdb.connect().execute(
        f"select min(wfir_risks), max(wfir_risks), min(wfir_afreq), max(wfir_afreq), "
        f"min(wfir_ealt) from '{NRI_ZIP}'").fetchone()
    assert 0 <= r[0] and r[1] <= 100, f"wfir_risks out of [0,100]: {r[:2]}"
    assert 0 <= r[2] and r[3] <= 0.1, f"wfir_afreq out of [0,0.1]: {r[2:4]}"
    assert r[4] >= 0, f"negative wfir_ealt: {r[4]}"
