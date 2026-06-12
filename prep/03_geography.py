"""prep/03_geography.py — resolve all spatial relationships to keys (J1-J3).

This is the ONLY place geometry runs for the cell/ZIP/county layer. Everything
downstream (and the deployed app) does key lookups. All area math is in EPSG:5070
(CONUS Albers, equal-area). Inputs: the GEFF spine's cell list +
$FIRELENS_DATA/raw/tiger/{county,zcta520}. Outputs (interim/):
  cell_membership.parquet  (cell_id, in_ca)            -- every spine cell, classified (J1)
  cell_meta.parquet        (cell_id, lat, lon, county_fips, land_frac)  -- in-CA cells
  zip_meta.parquet         (zip, lat, lon, county_fips)                 -- CA ZCTAs (G7)
  zip_cell_map.parquet     (zip, cell_id, weight)       -- area-weighted, sums to 1.0 (J2)

Run:  python prep/03_geography.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from prep import fields, paths

ALBERS = 5070
CA_STATEFP = "06"
BUFFER_M = 10_000  # 10 km membership buffer (DATA.md Part B 1.0 / J1)


def _spine_cells():
    con = duckdb.connect()
    spine = paths.INTERIM / "geff_spine.parquet"
    ids = con.execute(f"select distinct cell_id from '{spine}'").df()["cell_id"].to_numpy()
    lat, lon = fields.cell_to_latlon(ids)
    # 0.25-deg cell boxes in lon/lat, then to equal-area
    geoms = [box(x - 0.125, y - 0.125, x + 0.125, y + 0.125) for x, y in zip(lon, lat)]
    g = gpd.GeoDataFrame(
        {"cell_id": ids.astype("int64"), "lat": lat, "lon": lon},
        geometry=geoms, crs=4326,
    ).to_crs(ALBERS)
    g["cell_area"] = g.geometry.area
    return g


def _tiger():
    cp = paths.DATA_ROOT / "raw" / "tiger" / "tl_2024_us_county.zip"
    zp = paths.DATA_ROOT / "raw" / "tiger" / "tl_2024_us_zcta520.zip"
    counties = gpd.read_file(f"zip://{cp}")
    counties = counties[counties["STATEFP"] == CA_STATEFP][["GEOID", "NAME", "geometry"]].to_crs(ALBERS)
    counties["geometry"] = counties.geometry.buffer(0)  # heal any invalid rings

    zcta = gpd.read_file(f"zip://{zp}")
    z = pd.to_numeric(zcta["ZCTA5CE20"], errors="coerce")
    zcta = zcta[(z >= 90000) & (z <= 96162)].copy()  # CA ZIP-prefix prefilter (96162 = Truckee, max CA ZCTA; excludes HI 967xx)
    zcta = zcta.rename(columns={"ZCTA5CE20": "zip"})
    zcta["lat"] = pd.to_numeric(zcta["INTPTLAT20"], errors="coerce")
    zcta["lon"] = pd.to_numeric(zcta["INTPTLON20"], errors="coerce")
    zcta = zcta[["zip", "lat", "lon", "geometry"]].to_crs(ALBERS)
    zcta["geometry"] = zcta.geometry.buffer(0)
    return counties, zcta


def _majority_county(parts_gdf, key, counties):
    """argmax-area county GEOID per `key` via overlay; returns DataFrame[key, county_fips]."""
    ov = gpd.overlay(parts_gdf[[key, "geometry"]], counties[["GEOID", "geometry"]],
                     how="intersection", keep_geom_type=True)
    ov["a"] = ov.geometry.area
    idx = ov.groupby(key)["a"].idxmax()
    return ov.loc[idx, [key, "GEOID"]].rename(columns={"GEOID": "county_fips"})


def build():
    cells = _spine_cells()
    counties, zcta = _tiger()
    ca = counties.geometry.union_all()
    ca_buf = ca.buffer(BUFFER_M)

    # --- J1: membership for EVERY spine cell, then land_frac for in-CA ones -----
    cells["in_ca"] = cells.geometry.intersects(ca_buf)
    inca = cells[cells["in_ca"]].copy()
    inca["land_frac"] = (inca.geometry.intersection(ca).area / inca["cell_area"]).clip(0, 1)

    # --- J3: cell -> majority-area county (nearest-county fallback for buffer-only)
    cc = _majority_county(inca, "cell_id", counties)
    inca = inca.merge(cc, on="cell_id", how="left")
    missing = inca["county_fips"].isna()
    if missing.any():
        cgeo = counties.set_index("GEOID").geometry
        for i in inca.index[missing]:
            d = cgeo.distance(inca.at[i, "geometry"])
            inca.at[i, "county_fips"] = d.idxmin()

    cell_meta = inca[["cell_id", "lat", "lon", "county_fips", "land_frac"]].copy()
    cell_meta["cell_id"] = cell_meta["cell_id"].astype("int32")

    # --- J2: zip x cell area weights (over land cells), normalized to sum 1.0 ----
    ov = gpd.overlay(zcta[["zip", "geometry"]], cells[["cell_id", "geometry"]],
                     how="intersection", keep_geom_type=True)
    ov["a"] = ov.geometry.area
    tot = ov.groupby("zip")["a"].transform("sum")
    ov["weight"] = ov["a"] / tot
    zip_cell_map = ov[["zip", "cell_id", "weight"]].copy()
    zip_cell_map["cell_id"] = zip_cell_map["cell_id"].astype("int32")

    # --- zip_meta: centroid (lat/lon, degrees) + majority county (G7) -----------
    zc = _majority_county(zcta, "zip", counties)
    zip_meta = zcta[["zip", "lat", "lon"]].merge(zc, on="zip", how="inner")

    # keep zip_meta to ZIPs that actually got a cell weight (no orphans served)
    zips_with_cells = set(zip_cell_map["zip"].unique())
    zip_meta = zip_meta[zip_meta["zip"].isin(zips_with_cells)].copy()

    membership = cells[["cell_id", "in_ca"]].copy()
    membership["cell_id"] = membership["cell_id"].astype("int32")

    out = paths.INTERIM
    membership.to_parquet(out / "cell_membership.parquet", index=False)
    cell_meta.to_parquet(out / "cell_meta.parquet", index=False)
    zip_meta.to_parquet(out / "zip_meta.parquet", index=False)
    zip_cell_map.to_parquet(out / "zip_cell_map.parquet", index=False)
    return cells, cell_meta, zip_meta, zip_cell_map


def report(cells, cell_meta, zip_meta, zip_cell_map):
    print("\n" + "=" * 64)
    print("GEOGRAPHY REPORT (J1-J3)")
    print("=" * 64)
    print(f"spine cells classified : {len(cells)}  (in-CA {int(cells['in_ca'].sum())}, "
          f"out {int((~cells['in_ca']).sum())})")
    print(f"cell_meta (in-CA)      : {len(cell_meta)} rows, "
          f"land_frac {cell_meta.land_frac.min():.2f}..{cell_meta.land_frac.max():.2f}")
    print(f"zip_meta (CA ZCTAs)    : {len(zip_meta)}")
    print(f"zip_cell_map           : {len(zip_cell_map)} (zip,cell) pairs")
    ref = {"95404": "Sonoma", "90272": "Los Angeles", "94558": "Napa",
           "94588": "Alameda", "92328": "Inyo"}
    print("reference ZIP -> county_fips:")
    for z, nm in ref.items():
        row = zip_meta[zip_meta["zip"] == z]
        fips = row["county_fips"].iloc[0] if len(row) else "MISSING"
        print(f"   {z} ({nm:12s}) -> {fips}")
    print("=" * 64)


if __name__ == "__main__":
    report(*build())
