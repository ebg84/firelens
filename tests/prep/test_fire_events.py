"""Module 6 FRAP completeness gate (red until prep/06_pairing.py produces the
FRAP intermediate). Encodes the 2026-06-12 first-contact recon as a standing
guard: feature count, 1878->2025 span, the 2025 anchors, rxburn exclusion, and
GlobalID-derived fire_id uniqueness.

These assert against interim/frap_perimeters.parquet — the cleaned firep25_1
ingest (rxburn25_1 layer excluded), reprojected from EPSG:3310, fire_id minted
from the unique GlobalID. The fire_events statistics table (FPA-FOD 1992-2020 +
FRAP 2021+, F2) is gated separately once both sources are wired.
"""
import duckdb

from prep import paths

FRAP = paths.INTERIM / "frap_perimeters.parquet"


def _require():
    assert FRAP.exists(), "missing frap_perimeters.parquet — run prep/06_pairing.py first"


def test_frap_feature_count():
    """firep25_1 had 23,334 features; a count far above the firep-only band would
    mean the excluded rxburn layer leaked in."""
    _require()
    n = duckdb.connect().execute(f"select count(*) from '{FRAP}'").fetchone()[0]
    assert 15000 <= n <= 28000, f"FRAP perimeter count {n} outside firep-only band [15000, 28000]"


def test_frap_year_span():
    _require()
    lo, hi = duckdb.connect().execute(f"select min(year), max(year) from '{FRAP}'").fetchone()
    assert lo <= 1880, f"earliest year {lo} (expected ~1878)"
    assert hi >= 2025, f"latest year {hi} (expected 2025)"


def test_frap_2025_anchors_present():
    _require()
    con = duckdb.connect()
    for name in ("PALISADES", "EATON"):
        row = con.execute(
            f"select acres from '{FRAP}' where upper(name) = '{name}' and year = 2025"
        ).fetchone()
        assert row is not None, f"{name} 2025 missing from FRAP"
        assert row[0] and row[0] > 0, f"{name} 2025 has no acreage"


def test_frap_rxburn_excluded():
    """Only the firep layer is ingested; the source tag must never be a burn."""
    _require()
    bad = duckdb.connect().execute(
        f"select count(*) from '{FRAP}' where upper(source) like '%RX%' or upper(source) like '%BURN%'"
    ).fetchone()[0]
    assert bad == 0, f"{bad} prescribed-burn (rxburn) rows leaked in"


def test_frap_fire_id_unique():
    """GlobalID was 100% unique across 23,334 features -> fire_id must be too."""
    _require()
    con = duckdb.connect()
    n, u, nn = con.execute(
        f"select count(*), count(distinct fire_id), count(fire_id) from '{FRAP}'"
    ).fetchone()
    assert u == n, f"fire_id not unique: {u} distinct of {n}"
    assert nn == n, f"{n - nn} null fire_id"
