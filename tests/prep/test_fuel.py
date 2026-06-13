"""Module 8c — LANDFIRE FBFM40 fuel composition gate.

Critical correctness: non-burnable masked before burnable composition (but reported
separately), fractions sum to 1.0, CRS-matched zonal, coverage of the canonical ZCTAs.
"""
import glob

import duckdb

from prep import fuel, paths

FUEL = paths.INTERIM / "fuel_context.parquet"
BURN = ["grass", "grass_shrub", "shrub", "timber_understory", "timber_litter", "slash_blowdown"]


# ---- mapping oracle (runs now, reads the .vat) -------------------------------

def test_fbfm_mapping_read_from_vat():
    dbf = glob.glob(str(paths.DATA_ROOT / "raw" / "landfire" / "*.vat.dbf"))[0]
    vg = fuel.fbfm_groups(dbf)
    assert vg[91] == "non_burnable" and vg[99] == "non_burnable"
    assert vg[101] == "grass" and vg[141] == "shrub"
    assert vg[181] == "timber_litter" and vg[201] == "slash_blowdown"


# ---- gate (red until prep/10_fuel.py runs) -----------------------------------

def _require():
    assert FUEL.exists(), "missing fuel_context.parquet — run prep/10_fuel.py first"


def test_burnable_composition_sums_to_one():
    """Burnable group fractions (non-burnable masked) sum to ~1.0 where any burnable exists."""
    _require()
    s = " + ".join(f"{g}_frac" for g in BURN)
    bad = duckdb.connect().execute(
        f"select count(*) from '{FUEL}' where burnable_frac > 0 and abs(({s}) - 1.0) > 1e-3"
    ).fetchone()[0]
    assert bad == 0, f"{bad} ZIPs whose burnable composition != 1.0"


def test_burnable_plus_nonburnable_is_one():
    _require()
    bad = duckdb.connect().execute(
        f"select count(*) from '{FUEL}' where total_px > 0 and "
        f"abs(burnable_frac + non_burnable_frac - 1.0) > 1e-6").fetchone()[0]
    assert bad == 0, f"{bad} ZIPs where burnable+non_burnable != 1.0"


def test_non_burnable_reported_separately():
    _require()
    cols = duckdb.connect().execute(f"select * from '{FUEL}' limit 0").df().columns.tolist()
    assert "non_burnable_frac" in cols and "burnable_frac" in cols


def test_coverage_of_canonical_zctas():
    _require()
    con = duckdb.connect()
    n = con.execute(f"select count(*) from '{FUEL}'").fetchone()[0]
    canon = con.execute(f"select count(*) from '{paths.INTERIM/'zip_meta.parquet'}'").fetchone()[0]
    assert n / canon >= 0.95, f"fuel coverage {n}/{canon}"


def test_dominant_class_valid():
    _require()
    bad = duckdb.connect().execute(
        f"select count(*) from '{FUEL}' where dominant_class not in "
        f"('grass','grass_shrub','shrub','timber_understory','timber_litter','slash_blowdown','non_burnable')"
    ).fetchone()[0]
    assert bad == 0
