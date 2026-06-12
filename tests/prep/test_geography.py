"""Tier 1/2 geography tests for prep/03_geography.py (joins J1-J3).

Run RED before implementation, GREEN after. All spatial computation is prep-side
in EPSG:5070; these tests read only the resulting key tables (the zero-geometry
rule — the app, and these gates, do key lookups, never geometry).
"""
import duckdb

from prep import paths

CELL_META = paths.INTERIM / "cell_meta.parquet"
ZIP_META = paths.INTERIM / "zip_meta.parquet"
ZIP_CELL = paths.INTERIM / "zip_cell_map.parquet"
MEMBERSHIP = paths.INTERIM / "cell_membership.parquet"
SPINE = paths.INTERIM / "geff_spine.parquet"

# J3 spot-checks: reference ZIP -> majority-area county FIPS
REF_COUNTY = {
    "95404": "06097",  # Sonoma
    "90272": "06037",  # Los Angeles
    "94558": "06055",  # Napa
    "94588": "06001",  # Alameda
    "92328": "06027",  # Inyo (Death Valley)
}


def _require(*ps):
    for p in ps:
        assert p.exists(), f"missing {p.name} — run prep/03_geography.py first"


def test_zip_cell_weights_sum_to_one():
    """J2: area-weighted zip->cell weights must sum to 1.0 per ZIP."""
    _require(ZIP_CELL)
    con = duckdb.connect()
    bad = con.execute(
        f"select zip, sum(weight) s from '{ZIP_CELL}' group by zip "
        f"having abs(sum(weight) - 1.0) > 1e-6"
    ).fetchall()
    assert not bad, f"{len(bad)} ZIPs whose weights != 1.0, e.g. {bad[:5]}"


def test_every_zip_has_at_least_one_cell():
    _require(ZIP_META, ZIP_CELL)
    con = duckdb.connect()
    orphan = con.execute(
        f"select count(*) from '{ZIP_META}' z "
        f"where not exists (select 1 from '{ZIP_CELL}' m where m.zip = z.zip)"
    ).fetchone()[0]
    assert orphan == 0, f"{orphan} ZIPs with no cell"


def test_land_frac_in_unit_range():
    _require(CELL_META)
    con = duckdb.connect()
    lo, hi = con.execute(
        f"select min(land_frac), max(land_frac) from '{CELL_META}'"
    ).fetchone()
    assert 0.0 <= lo and hi <= 1.0, f"land_frac out of [0,1]: ({lo}, {hi})"


def test_reference_zip_counties():
    """J3: the five reference ZIPs land in the right county."""
    _require(ZIP_META)
    con = duckdb.connect()
    for z, fips in REF_COUNTY.items():
        row = con.execute(
            f"select county_fips from '{ZIP_META}' where zip = '{z}'"
        ).fetchone()
        assert row is not None, f"{z} absent from zip_meta"
        assert row[0] == fips, f"{z}: expected county {fips}, got {row[0]}"


def test_no_orphan_spine_cells():
    """J1: every spine cell is classified in-CA or out-of-CA — none unaccounted."""
    _require(MEMBERSHIP, CELL_META, SPINE)
    con = duckdb.connect()
    spine = con.execute(f"select count(distinct cell_id) from '{SPINE}'").fetchone()[0]
    classified = con.execute(
        f"select count(distinct cell_id) from '{MEMBERSHIP}'"
    ).fetchone()[0]
    assert classified == spine, f"{spine - classified} spine cells unclassified (orphans)"
    inca_mem = con.execute(
        f"select count(*) from '{MEMBERSHIP}' where in_ca"
    ).fetchone()[0]
    inca_meta = con.execute(f"select count(*) from '{CELL_META}'").fetchone()[0]
    assert inca_mem == inca_meta, f"cell_meta ({inca_meta}) != in-CA membership ({inca_mem})"
