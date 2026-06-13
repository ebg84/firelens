"""prep/10_fuel.py — LANDFIRE FBFM40 fuel composition per ZIP (Module 8c runner).

Reads the GeoTIFF + .vat (code→class), reprojects the canonical ZCTAs to the RASTER's
own CRS (verify, don't assume 5070), and computes per-ZIP fuel composition. Additive,
interim; folds into the served layer via re-export. Spine untouched.

Run:  python prep/10_fuel.py
"""
import glob
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb
import geopandas as gpd
import rasterio

from prep import fuel, paths


def main():
    lf = paths.DATA_ROOT / "raw" / "landfire"
    tif = glob.glob(str(lf / "*.tif"))[0]
    dbf = glob.glob(str(lf / "*.vat.dbf"))[0]
    value_group = fuel.fbfm_groups(dbf)

    served = set(duckdb.connect().execute(
        f"select zip from '{paths.INTERIM/'zip_meta.parquet'}'").df()["zip"])
    tig = paths.DATA_ROOT / "raw" / "tiger" / "tl_2024_us_zcta520.zip"
    z = gpd.read_file(f"zip://{tig}")
    z = z[z["ZCTA5CE20"].isin(served)].rename(columns={"ZCTA5CE20": "zip"})[["zip", "geometry"]]

    with rasterio.open(tif) as r:
        rcrs = r.crs
    z = z.to_crs(rcrs)                      # MATCH the raster CRS (custom CA Albers), not 5070
    assert z.crs == rcrs, "CRS mismatch — zonal stats would be wrong (the #1 bug)"
    print(f"zonal: {len(z)} ZCTAs over {tif.split('/')[-1]}; raster CRS matched "
          f"({rcrs.to_string()[:40]}...)", flush=True)

    comp = fuel.composition(z, str(tif), value_group)
    comp.to_parquet(paths.INTERIM / "fuel_context.parquet", index=False)

    con = duckdb.connect()
    f = f"'{paths.INTERIM/'fuel_context.parquet'}'"
    n = con.execute(f"select count(*) from {f}").fetchone()[0]
    zero = con.execute(f"select count(*) from {f} where burnable_frac = 0").fetchone()[0]
    print(f"fuel_context: {n}/{len(served)} ZCTAs | zero-burnable (all non-burnable): {zero}")
    print("\nsanity samples:")
    for label, col in [("HIGH TIMBER", "timber_litter_frac"), ("HIGH GRASS", "grass_frac"),
                       ("HIGH SHRUB", "shrub_frac"), ("MOST URBAN", "non_burnable_frac")]:
        r = con.execute(f"select zip, round({col},2), dominant_class, round(burnable_frac,2) "
                        f"from {f} order by {col} desc limit 1").fetchone()
        print(f"  {label:12s}: {r[0]} {col}={r[1]} dominant={r[2]} burnable_frac={r[3]}")


if __name__ == "__main__":
    main()
