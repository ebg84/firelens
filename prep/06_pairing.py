"""prep/06_pairing.py — occurrence ingest + fire-weather pairing (Module 6).

Builds three interim tables:
  fpa_fod.parquet         cleaned CA FPA-FOD fires (1992-2020), ign_date from
                          FIRE_YEAR + DISCOVERY_DOY (sidesteps the M/D/YYYY text)
  frap_perimeters.parquet cleaned firep25_1 (rxburn excluded), reprojected
                          3310->4326, fire_id from the unique GlobalID
  fire_events.parquet     paired stats: FPA-FOD <=2020 + FRAP >=2021 (F2 split),
                          >=300 ac, with fwi_pctile = percent-rank of the ignition
                          day's FWI within its (cell_id, iso_week) spine population.

FWI-only pairing (erc_pctile / structures_destroyed left null for now).
Run:  python prep/06_pairing.py
"""
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb
import geopandas as gpd
import pandas as pd

from prep import fields, paths


def ingest_fpa_fod():
    db = paths.INTERIM / "fpa_fod" / "FPA_FOD_20221014.sqlite"
    con = sqlite3.connect(db)
    df = pd.read_sql_query(
        """select FOD_ID, FIRE_NAME, FIRE_YEAR, DISCOVERY_DOY, NWCG_GENERAL_CAUSE,
                  FIRE_SIZE, FIRE_SIZE_CLASS, LATITUDE, LONGITUDE
           from Fires where STATE='CA'""", con)
    con.close()
    ign = (pd.to_datetime(df["FIRE_YEAR"].astype(str) + "-01-01")
           + pd.to_timedelta(df["DISCOVERY_DOY"].astype(int) - 1, unit="D"))
    lon = fields.to_signed_lon(df["LONGITUDE"].to_numpy(float))
    out = pd.DataFrame({
        "fire_id": "FOD-" + df["FOD_ID"].astype(str),
        "name": df["FIRE_NAME"],
        "year": df["FIRE_YEAR"].astype(int),
        "ign_date": ign.dt.date,
        "acres": df["FIRE_SIZE"].astype(float),
        "size_class": df["FIRE_SIZE_CLASS"],
        "cause_class": df["NWCG_GENERAL_CAUSE"],
        "lat": df["LATITUDE"].astype(float),
        "lon": df["LONGITUDE"].astype(float),
        "cell_id": fields.cell_id(df["LATITUDE"].to_numpy(float), lon).astype("int32"),
        "source": "FOD",
    })
    out.to_parquet(paths.INTERIM / "fpa_fod.parquet", index=False)
    return len(out)


def ingest_frap():
    zp = paths.DATA_ROOT / "raw" / "frap" / "fire251gdb.zip"
    gdf = gpd.read_file(f"/vsizip/{zp}/fire25_1.gdb", layer="firep25_1")  # EPSG:3310
    cent = gdf.geometry.centroid.to_crs(4326)  # centroid in equal-area, then to lon/lat
    lat, lon = cent.y.to_numpy(), cent.x.to_numpy()
    out = pd.DataFrame({
        "fire_id": "FRAP-" + gdf["GlobalID"].astype(str),
        "name": gdf["FIRE_NAME"],
        "year": pd.to_numeric(gdf["YEAR_"], errors="coerce"),
        "alarm_date": pd.to_datetime(gdf["ALARM_DATE"], errors="coerce").dt.date,
        "acres": pd.to_numeric(gdf["GIS_ACRES"], errors="coerce"),
        "lat": lat, "lon": lon,
        "cell_id": fields.cell_id(lat, fields.to_signed_lon(lon)).astype("int32"),
        "source": "FRAP",
    }).drop_duplicates(subset="fire_id")  # intra-FRAP dedup via GlobalID
    out.to_parquet(paths.INTERIM / "frap_perimeters.parquet", index=False)
    return len(out)


def pair():
    con = duckdb.connect()
    fpa = paths.INTERIM / "fpa_fod.parquet"
    frap = paths.INTERIM / "frap_perimeters.parquet"
    spine = paths.INTERIM / "geff_spine.parquet"
    cm = paths.INTERIM / "cell_meta.parquet"
    fe = paths.INTERIM / "fire_events.parquet"

    # F2: FPA-FOD stats <=2020 (>=300 ac = class E/F/G); FRAP stats >=2021 (>=300 ac)
    con.execute(f"""create temp table fires as
        select fire_id, name, ign_date, acres, lat, lon, cell_id, cause_class, source
        from read_parquet('{fpa}') where year between 1992 and 2020 and size_class in ('E','F','G')
        union all
        select fire_id, name, alarm_date ign_date, acres, lat, lon, cell_id,
               NULL cause_class, source
        from read_parquet('{frap}') where year >= 2021 and acres >= 300 and alarm_date is not null
    """)
    # spine with iso-week (week 53 -> 52)
    con.execute(f"""create temp table siw as
        select cell_id, case when week(date)=53 then 52 else week(date) end iw, date, fwi
        from read_parquet('{spine}')""")
    # each fire's own ignition-day FWI
    con.execute("""create temp table ff as
        select f.*, case when week(f.ign_date)=53 then 52 else week(f.ign_date) end iw,
               s.fwi fire_fwi
        from fires f left join siw s on s.cell_id=f.cell_id and s.date=f.ign_date""")
    # percent-rank within the (cell_id, iso_week) population
    con.execute("""create temp table pct as
        select ff.fire_id, avg(case when p.fwi <= ff.fire_fwi then 1.0 else 0.0 end) fwi_pctile
        from ff join siw p on p.cell_id=ff.cell_id and p.iw=ff.iw
        where ff.fire_fwi is not null
        group by ff.fire_id""")
    con.execute(f"""copy (
        select ff.fire_id, ff.name, ff.ign_date, ff.acres, ff.lat, ff.lon, ff.cell_id,
               cm.county_fips,
               pct.fwi_pctile,
               NULL::double erc_pctile,
               NULL::int structures_destroyed,
               ff.cause_class, ff.source
        from ff
        left join pct on pct.fire_id=ff.fire_id
        left join read_parquet('{cm}') cm on cm.cell_id=ff.cell_id
    ) to '{fe}' (format parquet)""")
    return con.execute(f"select count(*) from '{fe}'").fetchone()[0]


if __name__ == "__main__":
    print("FPA-FOD CA fires :", ingest_fpa_fod(), flush=True)
    print("FRAP perimeters  :", ingest_frap(), flush=True)
    n = pair()
    con = duckdb.connect()
    fe = paths.INTERIM / "fire_events.parquet"
    print("fire_events      :", n, flush=True)
    by = con.execute(f"select source, count(*), min(year(ign_date)), max(year(ign_date)) from '{fe}' group by 1").fetchall()
    for s, c, lo, hi in by:
        print(f"  {s}: {c} fires, {lo}-{hi}")
    t = con.execute(f"select fwi_pctile from '{fe}' where upper(name)='TUBBS' and year(ign_date)=2017").fetchone()
    print(f"  ANCHOR Tubbs 2017 FWI percentile: {t[0]:.3f}" if t and t[0] is not None else "  ANCHOR Tubbs: UNPAIRED")
