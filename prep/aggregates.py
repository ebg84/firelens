"""prep/aggregates.py — registry-driven aggregation (importable library).

The generic machinery: it iterates the metric registry and never names a metric.
build_annual / build_pctile_lut / build_zip_trends each process every registry
metric whose inputs are available in the data at hand, so the spine half runs now
(fwi/season_length/dc/erc) and the dailies half fills in later with zero code change.
prep/05_aggregates.py is the thin runner over the real spine.
"""
import duckdb
import pandas as pd

PCTS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
PCOLS = ["p10", "p20", "p30", "p40", "p50", "p60", "p70", "p80", "p90", "p95", "p99"]
BASELINE = (1980, 2000)
RECENT = (2010, 2100)


def _applicable(metric, columns):
    return set(metric.inputs).issubset(set(columns))


def primary_annual_col(metric):
    """The metric's primary annual column (first value column its annual_fn emits),
    discovered generically from a tiny synthetic frame — no metric is named here."""
    samp = pd.DataFrame({"cell_id": [1, 1],
                         "date": pd.to_datetime(["2001-01-01", "2001-01-02"]),
                         **{c: [1.0, 2.0] for c in metric.inputs}})
    out = metric.annual_fn(samp)
    return [c for c in out.columns if c not in ("cell_id", "year")][0]


def build_annual(registry, daily_df):
    """Merge every applicable metric's annual_fn output on (cell_id, year)."""
    cols = daily_df.columns
    merged = None
    for m in registry:
        if not _applicable(m, cols):
            continue
        a = m.annual_fn(daily_df)
        merged = a if merged is None else merged.merge(a, on=["cell_id", "year"], how="outer")
    return merged


def build_pctile_lut(registry, spine_path):
    """(cell_id, iso_week) quantile LUT for every percentile metric whose value is a
    spine column (passthrough). Derived-metric LUTs are handled with the dailies half."""
    con = duckdb.connect()
    have = con.execute(f"select * from read_parquet('{spine_path}') limit 0").df().columns.tolist()
    frames = []
    for m in registry:
        if not m.percentile or len(m.inputs) != 1 or m.inputs[0] not in have:
            continue
        col = m.inputs[0]
        df = con.execute(
            f"""select cell_id,
                       case when week(date)=53 then 52 else week(date) end as iso_week,
                       quantile_cont({col}, {PCTS}) as q
                from read_parquet('{spine_path}') where {col} is not null
                group by 1, 2""").df()
        p = pd.DataFrame(df["q"].tolist(), columns=PCOLS)
        out = pd.concat([df[["cell_id", "iso_week"]].reset_index(drop=True), p], axis=1)
        out.insert(0, "metric", m.name)
        frames.append(out)
    return pd.concat(frames, ignore_index=True)


def build_zip_trends(registry, annual_df, zip_cell_map):
    """Baseline-vs-recent trend per served metric, ZIP-weighted via zip_cell_map."""
    rows = []
    for m in registry:
        if not m.served:
            continue
        col = primary_annual_col(m)
        if col not in annual_df.columns:
            continue
        a = annual_df[["cell_id", "year", col]].merge(zip_cell_map, on="cell_id")
        a["wv"] = a[col] * a["weight"]
        zy = a.groupby(["zip", "year"]).agg(v=("wv", "sum"), w=("weight", "sum")).reset_index()
        zy["val"] = zy["v"] / zy["w"]
        base = zy[zy.year.between(*BASELINE)].groupby("zip")["val"].mean()
        rec = zy[zy.year.between(*RECENT)].groupby("zip")["val"].mean()
        t = pd.DataFrame({"baseline": base, "recent": rec}).dropna()
        t["pct_change"] = (t["recent"] - t["baseline"]) / t["baseline"]
        t["freq_ratio"] = t["recent"] / t["baseline"]
        t["metric"] = m.name
        t["robust"] = None  # bootstrap CI deferred
        rows.append(t.reset_index()[["zip", "metric", "baseline", "recent",
                                     "pct_change", "freq_ratio", "robust"]])
    return pd.concat(rows, ignore_index=True)
