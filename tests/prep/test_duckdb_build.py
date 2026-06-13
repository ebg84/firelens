"""DuckDB serving-DB build gate — the anti-drift guard for the GENERATED serving DB.

The DB is rebuilt from committed data/ and must EQUAL the source parquet. A weak diff
(row counts only) is theater; this asserts row counts, dtypes (silent coercion), NULL
counts per column (the 108 NRI-absent / 34 fuel-undefined / all-NULL claim columns), numeric
ranges, and ZIP key format (leading-zero preservation). RED on any drift, so a future
re-export that changes source is caught. Builds into a tmp path — never touches a real DB.
"""
import duckdb
import pytest

from prep import build_duckdb

# the full all-NULL set in the committed serving layer (claims-without-data — never fabricated)
EXPECTED_ALL_NULL = {"zip_trends.robust", "fire_events.erc_pctile", "fire_events.structures_destroyed"}


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    p = tmp_path_factory.mktemp("duckdb") / "firelens.duckdb"
    build_duckdb.build(db_path=p)
    return p


def test_diff_against_source_is_clean(db):
    """DB == source parquet on rowcount/dtype/NULL-count/range/ZIP-format. The core gate."""
    drifts = build_duckdb.diff_against_source(db)
    assert drifts == [], "DB drifted from source parquet:\n  " + "\n  ".join(drifts)


def test_all_null_columns_carried_through_not_fabricated(db):
    """All-NULL source columns stay 100% NULL (no fabricated fill). Pins the exact set so a
    future change — a new all-NULL column, or one of these getting fabricated — flips RED."""
    assert set(build_duckdb.all_null_columns(db)) == EXPECTED_ALL_NULL


def test_structures_destroyed_stays_null(db):
    """The meta-validation finding: structures_destroyed is 100% NULL and MUST NOT be filled."""
    con = duckdb.connect(str(db), read_only=True)
    nn = con.execute("select count(structures_destroyed) from fire_events").fetchone()[0]
    con.close()
    assert nn == 0, f"structures_destroyed fabricated: {nn} non-null"


def test_zip_serving_canonical_grain_and_one_row_per_zip(db):
    con = duckdb.connect(str(db), read_only=True)
    n, dz = con.execute("select count(*), count(distinct zip) from zip_serving").fetchone()
    con.close()
    assert n == 1801 and dz == 1801, f"zip_serving not 1,801 canonical / one-per-zip: {n}/{dz}"


def test_zip_serving_null_provenance(db):
    """NULL semantics carried honestly: NRI-absent (108) and fuel-undefined (34) as true NULLs,
    distinguishable from a real burnable_frac=0."""
    con = duckdb.connect(str(db), read_only=True)
    nri_null = con.execute("select count(*) from zip_serving where wfir_risks is null").fetchone()[0]
    quad_null = con.execute("select count(*) from zip_serving where quadrant is null").fetchone()[0]
    comp_null = con.execute("select count(*) from zip_serving where shrub_frac is null").fetchone()[0]
    real_zero = con.execute("select count(*) from zip_serving where burnable_frac=0").fetchone()[0]
    no_nan = con.execute("select count(*) from zip_serving where isnan(wfir_risks)").fetchone()[0]
    con.close()
    assert nri_null == 108 and quad_null == 108, f"NRI-absent != 108: {nri_null}/{quad_null}"
    assert comp_null == 34, f"fuel-undefined composition != 34 (22 no-raster + 12 nothing-burnable): {comp_null}"
    assert real_zero == 12, f"real burnable_frac=0 != 12: {real_zero}"
    assert no_nan == 0, "SQL NULL leaked as NaN — IS NULL semantics broken"


def test_zip_key_format_preserved(db):
    """Leading-zero ZIPs survive as 5-digit VARCHAR (the silent-key-coercion class)."""
    con = duckdb.connect(str(db), read_only=True)
    bad = con.execute("select count(*) from zip_serving where length(zip) != 5").fetchone()[0]
    con.close()
    assert bad == 0, f"{bad} ZIPs not 5-digit"


def test_metric_domains_contract_carried(db):
    """The coherence contract is queryable from the DB itself (grain/state per metric)."""
    con = duckdb.connect(str(db), read_only=True)
    n = con.execute("select count(*) from metric_domains").fetchone()[0]
    nri_state = con.execute("select state from metric_domains where metric='nri'").fetchone()[0]
    con.close()
    assert n >= 11 and nri_state == "additive"
