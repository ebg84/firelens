"""Tier 0.5 / Tier 1 tracer tests for the GEFF ingest (prep/01_ingest_geff.py).

The load-bearing test here is the F1 cell_id round-trip: GEFF NetCDFs store
east-positive 0-360 longitudes, while DATA.md's cell_id formula assumes signed
west-negative values. Feeding 0-360 straight into the formula double-shifts and
silently mis-registers every cell. test_cell_id_roundtrip_on_file_grid pins the
normalization by deriving cell_id from a file's OWN coordinates and asserting it
recovers those exact coordinates.
"""
import glob
import numpy as np
import pytest
import xarray as xr

from prep import fields, paths

GEFF_FILES = sorted(glob.glob(str(paths.RAW_GEFF / "*.nc")))
SPINE = paths.INTERIM / "geff_spine.parquet"


# ---- pure-function / first-contact tests (run immediately) -------------------

def test_geff_corpus_present():
    assert len(GEFF_FILES) >= 25, f"expected the multi-decade GEFF corpus, found {len(GEFF_FILES)}"


def test_corpus_year_coverage_is_gapless():
    """Derive year coverage from the corpus itself and assert 1940-2026 has no
    hole. A future file move/deletion that opened a gap would otherwise only
    surface weeks later as a subtle percentile shift."""
    covered = set()
    for f in GEFF_FILES:
        ds = xr.open_dataset(f)
        tname = "valid_time" if "valid_time" in ds.coords else "time"
        t = ds[tname].values
        ds.close()
        y0 = int(str(t.min())[:4])
        y1 = int(str(t.max())[:4])
        covered.update(range(y0, y1 + 1))
    missing = [y for y in range(1940, 2027) if y not in covered]
    assert not missing, f"year coverage gaps in 1940-2026: {missing}"


def test_canonical_var_map():
    # verified from the live files 2026-06-12
    assert fields.GEFF_VARS == {"fwinx": "fwi", "ercnfdr": "erc", "drtcode": "dc"}


def test_signed_lon_conversion():
    # the actual GEFF box edges: 235 E -> 125 W, 246.5 E -> 113.5 W
    assert fields.to_signed_lon(235.0) == -125.0
    assert fields.to_signed_lon(246.5) == -113.5
    # already-signed western values pass through unchanged (idempotent)
    assert fields.to_signed_lon(-125.0) == -125.0


def test_cell_id_roundtrip_on_file_grid():
    """F1: cell_id built from a file's own coords must round-trip to those coords."""
    ds = xr.open_dataset(GEFF_FILES[0])
    lat = ds["latitude"].values
    lon_signed = fields.to_signed_lon(ds["longitude"].values)
    ds.close()
    LON, LAT = np.meshgrid(lon_signed, lat)
    cid = fields.cell_id(LAT, LON)
    rlat, rlon = fields.cell_to_latlon(cid)
    assert np.allclose(rlat, LAT, atol=1e-9), "latitude failed to round-trip"
    assert np.allclose(rlon, LON, atol=1e-9), "longitude failed to round-trip (0-360 trap?)"


def test_naive_longitude_is_actually_wrong():
    """Guard the trap explicitly: applying the formula to raw 0-360 lon must NOT
    recover the true cell, proving the normalization is load-bearing (H2)."""
    raw_lon = 235.0  # east-positive, as stored
    true_cid = fields.cell_id(38.5, fields.to_signed_lon(raw_lon))  # -125 W
    naive_cid = fields.cell_id(38.5, raw_lon)                       # bug: no normalize
    assert true_cid != naive_cid


# ---- spine tests (skip until prep/01_ingest_geff.py has produced the parquet) -

@pytest.mark.skipif(not SPINE.exists(), reason="run prep/01_ingest_geff.py first")
def test_spine_schema_and_physical_ranges():
    import duckdb
    con = duckdb.connect()
    cols = con.execute(f"select * from '{SPINE}' limit 0").df().columns.tolist()
    assert {"cell_id", "date", "fwi", "erc", "dc"}.issubset(cols), cols
    lo, hi = con.execute(f"select min(fwi), max(fwi) from '{SPINE}'").fetchone()
    # FWI is open-ended (Canadian FWI has no ceiling); the corpus reaches ~238 in
    # arid summer cells. The ceiling here is a unit-error sanity bound (a km/h-style
    # 3.6x or order-of-magnitude slip would blow past it), not a weather bound.
    assert lo >= 0 and hi < 500, f"FWI out of sane range [0,500): ({lo}, {hi})"


def _spine_unique_key():
    import duckdb
    con = duckdb.connect()
    return con.execute(
        f"select count(*) from (select cell_id, date from '{SPINE}' "
        f"group by 1, 2 having count(*) > 1)"
    ).fetchone()[0]


@pytest.mark.skipif(not SPINE.exists(), reason="run prep/01_ingest_geff.py first")
def test_spine_key_is_unique():
    assert _spine_unique_key() == 0, "duplicate (cell_id, date) rows in the spine"


@pytest.mark.skipif(not SPINE.exists(), reason="run prep/01_ingest_geff.py first")
def test_tubbs_anchor_fwi_present():
    """Tubbs ignited 2017-10-08 near Calistoga (Sonoma). Its nearest cell must
    carry a physical FWI that day. (The PERCENTILE anchor waits on the LUT module.)"""
    import duckdb
    con = duckdb.connect()
    sonoma_cell = int(fields.cell_id(38.61, -122.62))
    row = con.execute(
        f"select fwi from '{SPINE}' where cell_id = {sonoma_cell} "
        f"and date = DATE '2017-10-08'"
    ).fetchone()
    assert row is not None, "no spine row for the Tubbs cell/day"
    assert 0 < row[0] < 500, f"implausible Tubbs-day FWI: {row[0]}"
