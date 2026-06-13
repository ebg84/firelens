"""Tier-2 exact-value tests for the metric formulas + registry (prep/metrics.py).

These are oracle tests: each formula has a known answer from its published
standard (DATA.md Part B §1 / TESTING.md Tier 2). Run RED before metrics.py
exists, GREEN after.
"""
import pandas as pd
import pytest

from prep import metrics as M


# ---- pure daily formulas -----------------------------------------------------

def test_rh_known_value():
    # T=30C, Td=10C -> RH ~28.9% (Magnus, Alduchov & Eskridge 1996)
    assert abs(M.rh_min(30.0, 10.0) - 28.9) < 0.5


def test_rh_saturation():
    assert M.rh_min(20.0, 20.0) == pytest.approx(100.0, abs=1e-6)


def test_vpd_known_value():
    assert abs(M.vpd_max(35.0, 5.0) - 4.75) < 0.05  # kPa


def test_vpd_floor_nonnegative():
    assert M.vpd_max(5.0, 20.0) == 0.0  # Td > T -> floored at 0


def test_red_flag_boundaries():
    assert bool(M.red_flag_day(12.0, 20.0)) is True
    assert bool(M.red_flag_day(10.9, 20.0)) is False   # wind below 11.18 m/s
    assert bool(M.red_flag_day(12.0, 26.0)) is False   # RH above 25%


def test_dry_day_threshold():
    assert bool(M.is_dry_day(0.9)) is True
    assert bool(M.is_dry_day(1.0)) is False  # WMO: <1.0 mm is dry


def test_fire_weather_threshold():
    assert bool(M.fire_weather_day(21.3)) is True   # EFFIS "high" lower bound
    assert bool(M.fire_weather_day(21.2)) is False


def test_iso_week_merge():
    assert M.iso_week("2017-10-08") == 40            # Tubbs day
    assert M.iso_week("2015-12-31") == 52            # week 53 merged into 52


# ---- annual aggregations (the non-trivial ones) ------------------------------

def test_cdd_run_crosses_year_boundary():
    # Dec 20 (2000) .. Jan 15 (2001) all dry = one 27-day run, assigned to 2001
    dates = pd.date_range("2000-12-20", "2001-01-15", freq="D")
    df = pd.DataFrame({"cell_id": 1, "date": dates.date, "precip": 0.0})
    out = M.cdd_annual(df)
    assert int(out.loc[out.year == 2001, "cdd_max"].iloc[0]) == 27
    assert set(out.year) == {2001}  # whole cross-year run lands in the later year


def test_cdd_dry_threshold_breaks_run():
    dates = pd.date_range("2001-06-01", periods=5, freq="D")
    df = pd.DataFrame({"cell_id": 1, "date": dates.date,
                       "precip": [0.9, 0.9, 1.0, 0.9, 0.9]})  # 1.0 mm is wet, breaks the run
    out = M.cdd_annual(df)
    assert int(out["cdd_max"].max()) == 2


def test_season_length_counts_fire_weather_days():
    df = pd.DataFrame({"cell_id": 1,
                       "date": pd.date_range("2001-01-01", periods=5, freq="D").date,
                       "fwi": [10.0, 21.3, 30.0, 21.2, 50.0]})
    out = M.season_length_annual(df)
    assert int(out["season_len"].iloc[0]) == 3  # 21.3, 30, 50 qualify


# ---- the registry contract ---------------------------------------------------

def test_registry_order_is_deterministic():
    names = [m.name for m in M.REGISTRY]
    assert names[:5] == ["fwi", "vpd", "dry_wind_days", "cdd", "season_length"]


def test_v1_served_and_candidates():
    served = {m.name for m in M.REGISTRY if m.served}
    # dc_pctile promoted to v1 (2026-06-12); erc_annual is the lone remaining candidate
    assert served == {"fwi", "vpd", "dry_wind_days", "cdd", "season_length", "dc_pctile"}
    candidates = {m.name for m in M.REGISTRY if not m.served}
    assert candidates == {"erc_annual"}


def test_registry_names_unique_and_cited():
    names = [m.name for m in M.REGISTRY]
    assert len(names) == len(set(names))
    for m in M.REGISTRY:
        assert m.formula_ref, f"{m.name} has no formula citation"
        assert m.claim_shape, f"{m.name} has no claim shape"
