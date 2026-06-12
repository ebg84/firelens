"""Module 6 pairing gate — fire_events (FPA-FOD 1992-2020 + FRAP 2021+, F2 split)
with FWI percentiles from the spine. Includes THE anchor: Tubbs ignited on a
>=90th-percentile fire-weather day. Red until prep/06_pairing.py runs.
"""
import duckdb

from prep import paths

FE = paths.INTERIM / "fire_events.parquet"


def _require():
    assert FE.exists(), "missing fire_events.parquet — run prep/06_pairing.py first"


def test_f2_era_split():
    """F2: stats take FPA-FOD only <=2020, FRAP only >=2021 — no crossover."""
    _require()
    bad = duckdb.connect().execute(
        f"""select count(*) from '{FE}' where
            (source='FOD' and year(ign_date) > 2020) or
            (source='FRAP' and year(ign_date) < 2021)"""
    ).fetchone()[0]
    assert bad == 0, f"{bad} F2 era-split violations"


def test_no_duplicate_fire_id():
    _require()
    n, u = duckdb.connect().execute(
        f"select count(*), count(distinct fire_id) from '{FE}'").fetchone()
    assert n == u, f"duplicate fire_ids: {u} distinct of {n}"


def test_fwi_pctile_in_unit_range():
    _require()
    bad = duckdb.connect().execute(
        f"select count(*) from '{FE}' where fwi_pctile is not null and (fwi_pctile < 0 or fwi_pctile > 1)"
    ).fetchone()[0]
    assert bad == 0, f"{bad} fwi_pctile out of [0,1]"


def test_tubbs_anchor_ge_90th_percentile():
    """THE anchor (Tier 3): Tubbs 2017-10-08 ignited on a >=90th-percentile FWI day
    for its Sonoma cell. If this fails, nothing else matters until it passes."""
    _require()
    r = duckdb.connect().execute(
        f"select fwi_pctile from '{FE}' where upper(name)='TUBBS' and year(ign_date)=2017"
    ).fetchone()
    assert r is not None and r[0] is not None, "Tubbs not paired to an FWI percentile"
    assert r[0] >= 0.90, f"Tubbs FWI percentile {r[0]:.3f} < 0.90"


def test_palisades_eaton_in_frap_era():
    _require()
    con = duckdb.connect()
    for name in ("PALISADES", "EATON"):
        r = con.execute(
            f"select source, year(ign_date) from '{FE}' where upper(name)='{name}'").fetchone()
        assert r is not None, f"{name} missing from fire_events"
        assert r[0] == 'FRAP' and r[1] == 2025, f"{name}: expected FRAP/2025, got {r}"
