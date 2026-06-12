"""Module 6 FPA-FOD completeness gate (red until prep/06_pairing.py produces the
cleaned table). Encodes the 2026-06-12 recon: CA count band, 1992-2020 span,
field spellings, the M/D/YYYY date parse (NOT Julian), and TUBBS presence.
"""
import duckdb

from prep import paths

FPA = paths.INTERIM / "fpa_fod.parquet"


def _require():
    assert FPA.exists(), "missing fpa_fod.parquet — run prep/06_pairing.py first"


def test_ca_count_band():
    _require()
    n = duckdb.connect().execute(f"select count(*) from '{FPA}'").fetchone()[0]
    assert 150000 <= n <= 350000, f"CA fire count {n} outside band (recon: 251,881)"


def test_year_span_exact():
    _require()
    lo, hi = duckdb.connect().execute(f"select min(year), max(year) from '{FPA}'").fetchone()
    assert lo == 1992 and hi == 2020, f"span {lo}-{hi} (expected 1992-2020)"


def test_pairing_fields_present():
    _require()
    cols = duckdb.connect().execute(f"select * from '{FPA}' limit 0").df().columns.tolist()
    for c in ["fire_id", "name", "ign_date", "acres", "size_class", "cause_class",
              "lat", "lon", "cell_id", "year"]:
        assert c in cols, f"{c} missing ({cols})"


def test_discovery_date_parsed_not_julian():
    """DISCOVERY_DATE is M/D/YYYY text; ign_date must be real dates inside 1992-2020,
    never a Julian-day misparse landing in some absurd year."""
    _require()
    bad = duckdb.connect().execute(
        f"select count(*) from '{FPA}' where year(ign_date) not between 1992 and 2020"
    ).fetchone()[0]
    assert bad == 0, f"{bad} fires with ign_date outside 1992-2020 (Julian misparse?)"


def test_tubbs_present_with_coords():
    _require()
    r = duckdb.connect().execute(
        f"select lat, lon, size_class from '{FPA}' where upper(name)='TUBBS' and year=2017"
    ).fetchone()
    assert r is not None, "TUBBS 2017 missing"
    assert abs(r[0] - 38.6) < 0.2 and abs(r[1] + 122.6) < 0.3, f"TUBBS coords off: {r}"
