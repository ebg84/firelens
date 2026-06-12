"""prep/01_ingest_geff.py — melt the GEFF NetCDF corpus to the weather spine.

Reads every $FIRELENS_DATA/raw/geff/*.nc, renames the three GEFF variables to the
canonical enum, derives cell_id from each file's OWN coordinates (F1, via the
0-360 -> signed normalization in fields.py), and streams the long
(cell_id, date, fwi, erc, dc) table to $FIRELENS_DATA/interim/geff_spine.parquet.
Ocean cells (FWI NaN by design) are dropped. Blocks tile time without overlap, so
(cell_id, date) is unique by construction; the test suite asserts it.

Run:  python prep/01_ingest_geff.py
"""
import glob
import pathlib
import sys

# Numbered scripts are run as `python prep/0N_*.py`; put the repo root on the
# path so `from prep import ...` resolves regardless of cwd.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr

from prep import fields, paths

ANCHORS = [
    ("Tubbs (Sonoma)", 38.61, -122.62, ["2017-10-08"]),
    ("Palisades (LA)", 34.07, -118.55, ["2025-01-07", "2025-01-08"]),
    ("Eaton (Altadena)", 34.19, -118.13, ["2025-01-07", "2025-01-08"]),
]


def ingest():
    files = sorted(glob.glob(str(paths.RAW_GEFF / "*.nc")))
    if not files:
        sys.exit(f"no GEFF NetCDFs under {paths.RAW_GEFF}")
    paths.INTERIM.mkdir(parents=True, exist_ok=True)
    out = paths.INTERIM / "geff_spine.parquet"

    writer = None
    rows_written = rows_seen = 0
    grid_step = None
    bbox = None
    for i, f in enumerate(files, 1):
        ds = xr.open_dataset(f).rename(fields.GEFF_VARS)
        tname = "valid_time" if "valid_time" in ds.coords else "time"
        lat = ds["latitude"].values
        if grid_step is None:
            grid_step = float(abs(np.diff(lat)[0]))
            bbox = (float(lat.min()), float(lat.max()),
                    float(fields.to_signed_lon(ds["longitude"].values).min()),
                    float(fields.to_signed_lon(ds["longitude"].values).max()))
        df = ds[["fwi", "erc", "dc"]].to_dataframe().reset_index()
        ds.close()
        rows_seen += len(df)
        df = df.dropna(subset=["fwi"])  # drop ocean cells
        lon_s = fields.to_signed_lon(df["longitude"].values)
        out_df = pd.DataFrame({
            "cell_id": fields.cell_id(df["latitude"].values, lon_s).astype("int32"),
            "date": pd.to_datetime(df[tname]).dt.date,
            "fwi": df["fwi"].astype("float32").values,
            "erc": df["erc"].astype("float32").values,
            "dc": df["dc"].astype("float32").values,
        })
        table = pa.Table.from_pandas(out_df, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(out, table.schema)
        writer.write_table(table)
        rows_written += len(out_df)
        print(f"  [{i:2d}/{len(files)}] {f.split('/')[-1]:42s} -> {len(out_df):>8,d} land rows")
    writer.close()
    return out, files, rows_seen, rows_written, grid_step, bbox


def tracer_report(out, files, rows_seen, rows_written, grid_step, bbox):
    import duckdb
    con = duckdb.connect()
    p = f"'{out}'"
    print("\n" + "=" * 72)
    print("TRACER REPORT — GEFF spine")
    print("=" * 72)
    print(f"files ingested      : {len(files)}")
    print(f"grid step           : {grid_step}°  (0.25° lattice, cell-center)")
    print(f"bbox (signed lon)   : lat {bbox[0]}..{bbox[1]}  lon {bbox[2]}..{bbox[3]}")
    print(f"rows seen / written : {rows_seen:,} -> {rows_written:,} "
          f"({100*rows_written/rows_seen:.1f}% land; ocean NaN dropped)")
    span = con.execute(f"select min(date), max(date) from {p}").fetchone()
    ncell = con.execute(f"select count(distinct cell_id) from {p}").fetchone()[0]
    lo, hi = con.execute(f"select min(fwi), max(fwi) from {p}").fetchone()
    dups = con.execute(
        f"select count(*) from (select cell_id,date from {p} group by 1,2 having count(*)>1)"
    ).fetchone()[0]
    print(f"date span           : {span[0]} -> {span[1]}")
    print(f"distinct cells       : {ncell}")
    print(f"FWI range           : {lo:.2f} .. {hi:.2f}  (physical [0,150])")
    print(f"duplicate (cell,date): {dups}")

    print("\nAnchor spot-checks (RAW FWI — percentile context comes after the LUT module):")
    for name, la, lo_, dates in ANCHORS:
        cid = int(fields.cell_id(la, lo_))
        rla, rlo = fields.cell_to_latlon(cid)
        print(f"  {name:18s} cell {cid} (center {rla:.2f}, {rlo:.2f}):")
        for d in dates:
            row = con.execute(
                f"select fwi, erc, dc from {p} where cell_id={cid} and date=DATE '{d}'"
            ).fetchone()
            if row:
                print(f"      {d}:  FWI={row[0]:6.2f}   ERC={row[1]:8.1f}   DC={row[2]:7.1f}")
            else:
                print(f"      {d}:  (no row)")
    print("=" * 72)


if __name__ == "__main__":
    tracer_report(*ingest())
