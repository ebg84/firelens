"""prep/05_aggregates.py — build annual_metrics, pctile_lut, zip_trends (spine half).

Registry-driven (prep/aggregates.py). Runs over the GEFF spine now; the dailies
metrics (vpd/dry_wind_days/cdd) fill in automatically once dailies.parquet exists.

Run:  python prep/05_aggregates.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb

from prep import aggregates, metrics, paths


def main():
    spine = paths.INTERIM / "geff_spine.parquet"
    con = duckdb.connect()

    # load the spine with reduced dtypes (float32) to keep the in-memory frame light
    daily = con.execute(
        f"""select cell_id, date, fwi::float fwi, erc::float erc, dc::float dc
            from read_parquet('{spine}')""").df()
    print(f"spine loaded: {len(daily):,} rows", flush=True)

    annual = aggregates.build_annual(metrics.REGISTRY, daily)
    del daily
    annual.to_parquet(paths.INTERIM / "annual_metrics.parquet", index=False)
    print(f"annual_metrics: {len(annual):,} rows, cols {list(annual.columns)}", flush=True)

    lut = aggregates.build_pctile_lut(metrics.REGISTRY, str(spine))
    lut.to_parquet(paths.INTERIM / "pctile_lut.parquet", index=False)
    print(f"pctile_lut: {len(lut):,} rows, metrics {sorted(lut.metric.unique())}", flush=True)

    zcm = con.execute(
        f"select zip, cell_id, weight from read_parquet('{paths.INTERIM/'zip_cell_map.parquet'}')").df()
    trends = aggregates.build_zip_trends(metrics.REGISTRY, annual, zcm)
    trends.to_parquet(paths.INTERIM / "zip_trends.parquet", index=False)
    print(f"zip_trends: {len(trends):,} rows, metrics {sorted(trends.metric.unique())}", flush=True)

    # report: the 95404 fwi trend (the demo headline)
    for met, fmt in [("fwi", ".1f"), ("season_length", ".0f")]:
        r = trends[(trends.zip == "95404") & (trends.metric == met)]
        if len(r):
            row = r.iloc[0]
            print(f"95404 {met}: baseline {row['baseline']:{fmt}} -> recent "
                  f"{row['recent']:{fmt}} ({row['pct_change']*100:+.1f}%)")


if __name__ == "__main__":
    main()
