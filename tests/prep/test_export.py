"""Module 7 export gate — the serving layer + manifest contract (RUBRIC R1).

Red until prep/07_export.py writes data/. Spine-now: fwi/season_length/dc_pctile
trends + LUTs + fire_events + geography; vpd/cdd/dry_wind_days pending-flagged.
"""
import glob
import json
import os

import duckdb

from prep import paths

DATA = paths.REPO_ROOT / "data"
MANIFEST = DATA / "manifest.json"
SERVED_TABLES = ["cell_meta", "zip_meta", "zip_cell_map", "annual_metrics",
                 "pctile_lut", "zip_trends", "fire_events"]


def _require():
    assert MANIFEST.exists(), "missing data/manifest.json — run prep/07_export.py first"


def test_tables_and_manifest_present():
    _require()
    m = json.load(open(MANIFEST))
    for t in SERVED_TABLES:
        assert (DATA / f"{t}.parquet").exists(), f"{t}.parquet missing"
        assert t in m["tables"], f"{t} missing from manifest"


def test_manifest_rowcounts_match_parquet():
    """F6: the manifest is the contract — counts must match the written files."""
    _require()
    m = json.load(open(MANIFEST))
    con = duckdb.connect()
    for t in SERVED_TABLES:
        n = con.execute(f"select count(*) from '{DATA / f'{t}.parquet'}'").fetchone()[0]
        assert m["tables"][t]["rows"] == n, f"{t}: manifest {m['tables'][t]['rows']} != {n}"


def test_size_under_100mb():
    _require()
    total = sum(os.path.getsize(p) for p in glob.glob(str(DATA / "**" / "*"), recursive=True)
                if os.path.isfile(p))
    assert total < 100 * 1024 * 1024, f"data/ is {total/1e6:.1f} MB (> 100)"


def test_restricted_to_in_ca_cells():
    """AUDIT [Med]: annual_metrics / pctile_lut must not ship out-of-CA spine cells."""
    _require()
    con = duckdb.connect()
    cm = DATA / "cell_meta.parquet"
    for t in ["annual_metrics", "pctile_lut"]:
        orphan = con.execute(
            f"select count(*) from '{DATA / f'{t}.parquet'}' "
            f"where cell_id not in (select cell_id from '{cm}')").fetchone()[0]
        assert orphan == 0, f"{t}: {orphan} out-of-CA cells exported"


def test_zip_trends_served_metrics():
    _require()
    mets = {r[0] for r in duckdb.connect().execute(
        f"select distinct metric from '{DATA / 'zip_trends.parquet'}'").fetchall()}
    assert {"fwi", "season_length", "dc_pctile"}.issubset(mets), mets


def test_pending_metrics_flagged_with_lanes():
    _require()
    m = json.load(open(MANIFEST))
    for met in ["vpd", "cdd", "dry_wind_days"]:
        assert met in m["pending_metrics"], f"{met} not pending-flagged"
        assert m["pending_metrics"][met].get("lane"), f"{met} has no lane"


def test_tubbs_anchor_survives_export():
    _require()
    r = duckdb.connect().execute(
        f"select fwi_pctile from '{DATA / 'fire_events.parquet'}' "
        f"where upper(name)='TUBBS' and year(ign_date)=2017").fetchone()
    assert r is not None and r[0] >= 0.90, f"Tubbs anchor lost in export: {r}"
