"""Module: spatial/temporal coherence ENFORCEMENT (Part 2).

Reads the manifest's metric_domains contract and verifies the ACTUAL parquets match
each metric's DECLARED grain — per-metric, never a universal 1,801 assert. If a future
join breaks coherence (a metric drifts off its declared grain/range), these go RED.
"""
import json

import duckdb

from prep import domains, paths

D = paths.REPO_ROOT / "data"
I = paths.INTERIM
MANIFEST = D / "manifest.json"


def _domains():
    return json.load(open(MANIFEST)).get("metric_domains", {})


def _canon():
    return {r[0] for r in duckdb.connect().execute(
        f"select distinct zip from '{D/'zip_meta.parquet'}'").fetchall()}


# ---- contract completeness ---------------------------------------------------

def test_every_metric_declares_full_domain_block():
    md = _domains()
    for name in domains.DOMAINS:
        assert name in md, f"{name} not declared in manifest.metric_domains"
        for field in domains.REQUIRED:
            assert md[name].get(field), f"{name} missing domain field '{field}'"


def test_firms_declared_pending_fuel_declared_additive():
    """Closes unguarded-risk #8: FIRMS still pending (declared, so a consumer shows
    'data pending'); fuel_context promoted to additive (joined via 8c raster zonal)."""
    md = _domains()
    assert md.get("firms_density", {}).get("state") == "pending", "firms_density not pending"
    assert md["firms_density"].get("blocked_on"), "firms_density missing blocked_on"
    assert md.get("fuel_context", {}).get("state") == "additive", "fuel_context not promoted to additive"


# ---- actual parquet matches declared grain (per-metric) ----------------------

def test_served_zip_metrics_match_canonical_set():
    """fwi/season_length/dc_pctile serve at ZIP via zip_trends — must equal canonical 1,801."""
    canon = _canon()
    zt = {r[0] for r in duckdb.connect().execute(
        f"select distinct zip from '{D/'zip_trends.parquet'}'").fetchall()}
    assert zt == canon, f"zip_trends ZIP set ({len(zt)}) != canonical ({len(canon)})"


def test_cell_grained_tables_subset_of_cell_meta():
    """annual_metrics / pctile_lut are cell-grained -> every cell_id must exist in cell_meta
    (the join path); a stray cell would mean a broken aggregation."""
    con = duckdb.connect()
    cm = D / "cell_meta.parquet"
    for t in ["annual_metrics", "pctile_lut"]:
        orphan = con.execute(
            f"select count(*) from (select distinct cell_id from '{D/f'{t}.parquet'}') "
            f"where cell_id not in (select cell_id from '{cm}')").fetchone()[0]
        assert orphan == 0, f"{t}: {orphan} cells not in cell_meta"


def test_fire_events_point_to_cell_in_range():
    con = duckdb.connect()
    orphan = con.execute(
        f"select count(*) from '{D/'fire_events.parquet'}' "
        f"where cell_id not in (select cell_id from '{D/'cell_meta.parquet'}')").fetchone()[0]
    # point events may snap to a border cell outside cell_meta; allow a small fraction
    total = con.execute(f"select count(*) from '{D/'fire_events.parquet'}'").fetchone()[0]
    assert orphan / total < 0.05, f"{orphan}/{total} fire cells off the CA cell grid"
    lo, hi = con.execute(
        f"select min(year(ign_date)), max(year(ign_date)) from '{D/'fire_events.parquet'}'").fetchone()
    assert 1992 <= lo and hi <= 2025, f"fire_events out of declared range: {lo}-{hi}"


def test_nri_matrix_declared_1693_with_expected_108_gap():
    """nri/matrix are ZIP(1693) by design — the 108 (104 non-res + 4 F8) gap is expected,
    NOT a coverage failure. Verify the actual set sits inside canonical with exactly that gap."""
    canon = _canon()
    con = duckdb.connect()
    for t in ["nri_zip", "zip_priority_matrix"]:
        p = I / f"{t}.parquet"
        if not p.exists():
            continue
        s = {r[0] for r in con.execute(f"select distinct zip from '{p}'").fetchall()}
        assert s <= canon, f"{t} has ZIPs outside canonical"
        assert len(canon - s) == 108, f"{t} gap is {len(canon-s)}, expected 108"


def test_temporal_granularity_not_finer_than_declared():
    """A metric declared annual/era/static must not carry a finer (daily 'date') time axis
    in its served table — guards against implying resolution that doesn't exist."""
    con = duckdb.connect()
    am_cols = con.execute(f"select * from '{D/'annual_metrics.parquet'}' limit 0").df().columns
    assert "year" in am_cols and "date" not in am_cols, "annual_metrics must be annual, not daily"
    zt_cols = con.execute(f"select * from '{D/'zip_trends.parquet'}' limit 0").df().columns
    assert "date" not in zt_cols and "year" not in zt_cols, "zip_trends is an era comparison, no time axis"
