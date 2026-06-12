"""prep/metrics.py — the Metric Extension Protocol (DATA.md Part B §4.5a).

The served metric set is a REGISTRY, not a hardcoded enum. Each metric is one
`Metric` record + its formula functions; the generic machinery (derived-daily ->
annual_metrics -> pctile_lut -> zip_trends -> export, plus the live "today" path)
iterates `REGISTRY` in this fixed order and never names a metric. Adding a metric
is one entry + its formula fns — no edit to LUT/trend/export/live code.

HARD LIMIT (descriptive-only): every metric traces to a published standard and is
a SINGLE measure. There is no path here to combine metrics. Forecasts, fire
behavior/spread, parcel claims, and composite/invented indices are banned.
"""
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pandas as pd

# ============================ pure daily formulas ============================
# Magnus saturation vapor pressure, Alduchov & Eskridge (1996); DATA.md §1.1.

def es(t_c):
    """Saturation vapor pressure (hPa) at temperature t_c (deg C)."""
    return 6.1094 * np.exp(17.625 * t_c / (t_c + 243.04))


def rh_min(t_max, td_mean):
    """RH_min (%) approximated from daily T_max and mean dewpoint (DATA.md §1.1)."""
    return np.clip(100.0 * es(td_mean) / es(t_max), 0.0, 100.0)


def vpd_max(t_max, td_mean):
    """VPD_max (kPa) from T_max and mean dewpoint, floored at 0 (DATA.md §1.1)."""
    return np.maximum((es(t_max) - es(td_mean)) / 10.0, 0.0)


RED_FLAG_WIND_MS = 11.18  # 25 mph sustained
RED_FLAG_RH = 25.0


def red_flag_day(wind_max_ms, rh_min_pct):
    """Red Flag-condition day (DATA.md §1.2). wind in m/s (UNITS GUARD)."""
    return (np.asarray(wind_max_ms) >= RED_FLAG_WIND_MS) & (np.asarray(rh_min_pct) <= RED_FLAG_RH)


DRY_DAY_MM = 1.0


def is_dry_day(precip_mm):
    """WMO dry-day convention: < 1.0 mm (DATA.md §1.3)."""
    return np.asarray(precip_mm) < DRY_DAY_MM


FIRE_WEATHER_FWI = 21.3   # EFFIS "high" lower bound
EXTREME_FWI = 38.0        # EFFIS "extreme"


def fire_weather_day(fwi):
    return np.asarray(fwi) >= FIRE_WEATHER_FWI


def iso_week(date_like):
    """ISO week with week 53 merged into 52 (DATA.md §1.5). Scalar or Series."""
    if np.ndim(date_like) == 0:
        w = pd.Timestamp(date_like).to_pydatetime().isocalendar()[1]
        return 52 if w == 53 else w
    w = pd.to_datetime(pd.Series(date_like)).dt.isocalendar().week.astype(int)
    return w.where(w != 53, 52)


# ============================ annual aggregations ============================
# Each returns a DataFrame keyed (cell_id, year) with this metric's annual
# column(s). The daily input frame carries (cell_id, date, <inputs>).

def _year(s):
    return pd.to_datetime(pd.Series(s)).dt.year.to_numpy()


def fwi_annual(df):
    g = df.assign(year=_year(df["date"])).groupby(["cell_id", "year"])
    out = g["fwi"].agg(fwi_mean="mean", fwi_max="max").reset_index()
    ext = (df.assign(year=_year(df["date"]), e=(np.asarray(df["fwi"]) >= EXTREME_FWI))
           .groupby(["cell_id", "year"])["e"].sum().reset_index(name="extreme_days"))
    return out.merge(ext, on=["cell_id", "year"])


def vpd_annual(df):
    v = vpd_max(np.asarray(df["t_max"], float), np.asarray(df["td_mean"], float))
    d = df.assign(year=_year(df["date"]), vpd=v)
    return d.groupby(["cell_id", "year"])["vpd"].mean().reset_index(name="vpd_max_mean")


def dry_wind_days_annual(df):
    rh = rh_min(np.asarray(df["t_max"], float), np.asarray(df["td_mean"], float))
    rf = red_flag_day(np.asarray(df["wind_max"], float), rh)
    d = df.assign(year=_year(df["date"]), rf=rf.astype(int))
    return d.groupby(["cell_id", "year"])["rf"].sum().reset_index(name="red_flag_days")


def cdd_annual(df):
    """Longest consecutive dry-day run ENDING in each year; cross-year runs honored."""
    d = df.sort_values(["cell_id", "date"]).copy()
    d["dry"] = is_dry_day(np.asarray(d["precip"], float))
    # a run breaks on each wet day: cumulative count of wet days is the run id
    d["run_id"] = (~d["dry"]).astype(int).groupby(d["cell_id"]).cumsum()
    runs = (d[d["dry"]].groupby(["cell_id", "run_id"])
            .agg(length=("date", "size"), end=("date", "max")).reset_index())
    runs["year"] = _year(runs["end"])
    return (runs.groupby(["cell_id", "year"])["length"].max()
            .reset_index(name="cdd_max"))


def season_length_annual(df):
    d = df.assign(year=_year(df["date"]), fwd=fire_weather_day(np.asarray(df["fwi"], float)).astype(int))
    return d.groupby(["cell_id", "year"])["fwd"].sum().reset_index(name="season_len")


def dc_annual(df):
    d = df.assign(year=_year(df["date"]))
    return d.groupby(["cell_id", "year"])["dc"].max().reset_index(name="dc_max")


def erc_annual(df):
    d = df.assign(year=_year(df["date"]))
    return d.groupby(["cell_id", "year"])["erc"].mean().reset_index(name="erc_mean")


# ============================ the registry ==================================

@dataclass(frozen=True)
class Metric:
    name: str
    unit: str
    tier: str                     # "v1" | "candidate" | "v1.1"
    served: bool
    inputs: tuple                 # daily/spine columns it reads
    daily_fn: Optional[Callable]  # per-(cell,date) value; None = taken straight from spine
    annual_fn: Callable           # (daily_df) -> DataFrame[cell_id, year, <cols>]
    percentile: bool              # gets a (cell, iso_week) weekly LUT?
    trend_kind: object            # "pct_change" | ("freq_ratio", threshold)
    degradation: Optional[str]    # per-metric fallback when a source is dark (G-series)
    live_fn: Optional[Callable]   # rank a single live forecast-day; None = not single-day rankable
    formula_ref: str
    claim_shape: str


# Explicit, fixed iteration order (renders deterministic everywhere).
REGISTRY = [
    Metric(
        name="fwi", unit="index", tier="v1", served=True,
        inputs=("fwi",), daily_fn=lambda df: df["fwi"], annual_fn=fwi_annual,
        percentile=True, trend_kind="pct_change", degradation="vpd_substitute",
        live_fn=lambda day: float(day["fwi"]),
        formula_ref="Van Wagner 1987 (GEFF/CEMS); EFFIS classes; DATA.md §1.4-1.5",
        claim_shape="the last five years rank in the {pctile}th percentile of every five-year window since 1940",
    ),
    Metric(
        name="vpd", unit="kPa", tier="v1", served=True,
        inputs=("t_max", "td_mean"),
        daily_fn=lambda df: vpd_max(np.asarray(df["t_max"], float), np.asarray(df["td_mean"], float)),
        annual_fn=vpd_annual, percentile=False, trend_kind="pct_change",
        degradation=None, live_fn=lambda day: float(vpd_max(day["t_max"], day["td_mean"])),
        formula_ref="Alduchov & Eskridge 1996 (Magnus); DATA.md §1.1",
        claim_shape="VPD_max averages {recent} kPa in {recent_era} vs {baseline} in the baseline ({pct_change})",
    ),
    Metric(
        name="dry_wind_days", unit="days/yr", tier="v1", served=True,
        inputs=("wind_max", "t_max", "td_mean"),
        daily_fn=lambda df: red_flag_day(
            np.asarray(df["wind_max"], float),
            rh_min(np.asarray(df["t_max"], float), np.asarray(df["td_mean"], float))),
        annual_fn=dry_wind_days_annual, percentile=False,
        trend_kind=("freq_ratio", None), degradation=None, live_fn=None,
        formula_ref="NWS Red Flag criteria (25 mph / 25% RH); DATA.md §1.2",
        claim_shape="{zip} averages {recent} Red Flag-condition days/yr in {recent_era} vs {baseline} ({pct_change}, {freq_ratio}x)",
    ),
    Metric(
        name="cdd", unit="days", tier="v1", served=True,
        inputs=("precip",), daily_fn=lambda df: is_dry_day(np.asarray(df["precip"], float)),
        annual_fn=cdd_annual, percentile=False, trend_kind=("freq_ratio", 30),
        degradation=None, live_fn=None,
        formula_ref="WMO dry-day convention (<1.0 mm); DATA.md §1.3",
        claim_shape="the longest dry spell here runs {recent} days vs {baseline} in the baseline era",
    ),
    Metric(
        name="season_length", unit="days/yr", tier="v1", served=True,
        inputs=("fwi",), daily_fn=lambda df: fire_weather_day(np.asarray(df["fwi"], float)),
        annual_fn=season_length_annual, percentile=False, trend_kind="pct_change",
        degradation="vpd_substitute", live_fn=None,
        formula_ref="EFFIS fire-weather-day (FWI>=21.3); DATA.md §1.4",
        claim_shape="the fire-weather season runs ~{delta} days longer than in the baseline era",
    ),
    # ---- candidates: defined so the machinery is exercised; served=False until a
    # ---- named gate after Module 05 (formula test + claim shape + docs that night).
    Metric(
        name="dc_pctile", unit="percentile", tier="candidate", served=False,
        inputs=("dc",), daily_fn=lambda df: df["dc"], annual_fn=dc_annual,
        percentile=True, trend_kind="pct_change", degradation=None,
        live_fn=lambda day: float(day["dc"]),
        formula_ref="Van Wagner 1987 Drought Code (GEFF); DATA.md §4.5a candidate",
        claim_shape="deep-drought (Drought Code) ranks in the {pctile}th percentile of the local record",
    ),
    Metric(
        name="erc_annual", unit="J/m^2", tier="candidate", served=False,
        inputs=("erc",), daily_fn=lambda df: df["erc"], annual_fn=erc_annual,
        percentile=False, trend_kind="pct_change", degradation=None, live_fn=None,
        formula_ref="US NFDRS Energy Release Component (GEFF); DATA.md §4.5a candidate",
        claim_shape="annual mean ERC has shifted {pct_change} from the baseline era",
    ),
]

BY_NAME = {m.name: m for m in REGISTRY}


def served_metrics():
    return [m for m in REGISTRY if m.served]
