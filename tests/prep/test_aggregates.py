"""Module 5 (spine half) aggregation tests — annual_metrics, pctile_lut, zip_trends.

The headline is test_dummy_metric_propagates_end_to_end: the extension-protocol
proof that a NEW registry entry flows through the generic machinery with zero edits
to the aggregator. The data tests are red until prep/05_aggregates.py runs over the
spine; the dummy-propagation test runs immediately on synthetic data.
"""
import pandas as pd
import pytest

from prep import aggregates, metrics, paths

ANNUAL = paths.INTERIM / "annual_metrics.parquet"
LUT = paths.INTERIM / "pctile_lut.parquet"
TRENDS = paths.INTERIM / "zip_trends.parquet"


def _require(*ps):
    for p in ps:
        assert p.exists(), f"missing {p.name} — run prep/05_aggregates.py first"


# ---- extension-protocol proof (synthetic, runs now) --------------------------

def test_dummy_metric_propagates_end_to_end():
    df = pd.DataFrame({
        "cell_id": [1, 1, 2, 2],
        "date": pd.to_datetime(["2001-01-01", "2001-01-02", "2001-01-01", "2001-01-02"]),
        "fwi": [10.0, 20.0, 30.0, 40.0],
    })
    dummy = metrics.Metric(
        name="dummy", unit="x", tier="v1", served=True, inputs=("fwi",),
        daily_fn=lambda d: d["fwi"],
        annual_fn=lambda d: (d.assign(year=pd.to_datetime(d["date"]).dt.year)
                             .groupby(["cell_id", "year"])["fwi"].mean()
                             .reset_index(name="dummy_val")),
        percentile=False, trend_kind="pct_change", degradation=None, live_fn=None,
        formula_ref="test", claim_shape="test")
    out = aggregates.build_annual([metrics.BY_NAME["fwi"], dummy], df)
    # the new metric's column appears with NO edit to build_annual
    assert "dummy_val" in out.columns
    assert "fwi_mean" in out.columns


# ---- annual_metrics ----------------------------------------------------------

def test_annual_has_spine_metric_columns():
    _require(ANNUAL)
    import duckdb
    cols = duckdb.connect().execute(f"select * from '{ANNUAL}' limit 0").df().columns.tolist()
    for c in ["cell_id", "year", "fwi_mean", "fwi_max", "extreme_days", "season_len",
              "dc_max", "erc_mean"]:
        assert c in cols, f"{c} missing from annual_metrics ({cols})"


def test_annual_sanity_and_non_degenerate():
    _require(ANNUAL)
    import duckdb
    con = duckdb.connect()
    assert con.execute(f"select count(*) from '{ANNUAL}' where fwi_max < fwi_mean").fetchone()[0] == 0
    lo, hi = con.execute(f"select min(season_len), max(season_len) from '{ANNUAL}'").fetchone()
    assert 0 <= lo and hi <= 366, (lo, hi)
    # non-degenerate: fwi_mean varies across cells (catches a broken join)
    assert con.execute(f"select count(distinct round(fwi_mean,2)) from '{ANNUAL}'").fetchone()[0] > 100


# ---- pctile_lut --------------------------------------------------------------

def test_lut_monotonic_and_complete():
    _require(LUT)
    import duckdb
    con = duckdb.connect()
    # non-decreasing (NOT strict: low-FWI winter weeks legitimately tie at/near 0)
    bad = con.execute(
        f"""select count(*) from '{LUT}' where metric='fwi' and not (
            p10<=p20 and p20<=p30 and p30<=p40 and p40<=p50 and p50<=p60 and
            p60<=p70 and p70<=p80 and p80<=p90 and p90<=p95 and p95<=p99)""").fetchone()[0]
    assert bad == 0, f"{bad} non-monotonic fwi LUT rows"
    nulls = con.execute(
        f"select count(*) from '{LUT}' where metric='fwi' and (p10 is null or p99 is null)").fetchone()[0]
    assert nulls == 0
    wk = con.execute(f"select min(iso_week), max(iso_week) from '{LUT}'").fetchone()
    assert wk[0] >= 1 and wk[1] <= 52, wk


def test_lut_exercises_candidate_machinery():
    _require(LUT)
    import duckdb
    mets = {r[0] for r in duckdb.connect().execute(f"select distinct metric from '{LUT}'").fetchall()}
    assert "fwi" in mets, mets
    assert "dc_pctile" in mets, "candidate dc_pctile LUT not built — machinery not exercised"


# ---- zip_trends --------------------------------------------------------------

def test_zip_trends_served_spine_metrics_only():
    _require(TRENDS)
    import duckdb
    con = duckdb.connect()
    mets = {r[0] for r in con.execute(f"select distinct metric from '{TRENDS}'").fetchall()}
    # dc_pctile promoted to v1; erc_annual remains a candidate (served=False)
    assert {"fwi", "season_length", "dc_pctile"}.issubset(mets), mets
    assert "erc_annual" not in mets
    row = con.execute(
        f"select pct_change from '{TRENDS}' where zip='95404' and metric='fwi'").fetchone()
    assert row is not None and row[0] is not None
