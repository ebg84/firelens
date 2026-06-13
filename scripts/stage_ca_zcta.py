"""Stage simplified CA ZCTA boundaries for the /explore map (event-built map asset).

Source: CalHHS-hosted Census 2020 NGDA ZCTA FeatureServer (national, 33,791 features),
queried FILTERED TO CALIFORNIA (ZCTA5 90001-96162) so only ~1,760 features transfer —
fast and robust. Server-side generalized via maxAllowableOffset. Vintage = 2020 (matches
our ZIP keys; 2010 had 33,120 ZCTAs, 2020 has 33,791). Keeps ONLY the ZCTA5 code as join
key, filters to the serving layer -> data/geo/ca_zcta.geojson.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import geopandas as gpd
import requests

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "geo" / "ca_zcta.geojson"
QUERY = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
    "Census_ZIP_Code_Tabulation_Areas_2010_v1/FeatureServer/0/query"
)
CA_WHERE = "ZCTA5 >= '90001' AND ZCTA5 <= '96162'"
PAGE = 2000


def fetch_ca() -> dict:
    feats: list = []
    offset = 0
    while True:
        params = {
            "where": CA_WHERE,
            "outFields": "ZCTA5",
            "returnGeometry": "true",
            "outSR": 4326,
            "maxAllowableOffset": 0.001,   # ~100 m server-side generalize
            "geometryPrecision": 5,
            "f": "geojson",
            "resultRecordCount": PAGE,
            "resultOffset": offset,
        }
        r = requests.get(QUERY, params=params, timeout=90)
        r.raise_for_status()
        fc = r.json()
        page = fc.get("features", [])
        feats.extend(page)
        print(f"  fetched {len(page)} (offset {offset}), total {len(feats)}")
        if len(page) < PAGE:
            break
        offset += PAGE
    return {"type": "FeatureCollection", "features": feats}


def main() -> int:
    serving = {
        r[0] for r in duckdb.connect(str(REPO / "firelens.duckdb"), read_only=True)
        .execute("select zip from zip_serving").fetchall()
    }
    print(f"serving ZIPs: {len(serving)}")
    print("querying CalHHS Census-2020 ZCTA, filtered to CA…")
    fc = fetch_ca()

    gdf = gpd.GeoDataFrame.from_features(fc["features"], crs=4326)
    gdf["zip"] = gdf["ZCTA5"].astype(str)
    print(f"CA ZCTAs fetched: {len(gdf)}")

    gdf = gdf[gdf["zip"].isin(serving)][["zip", "geometry"]].copy()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    gdf.to_file(OUT, driver="GeoJSON", COORDINATE_PRECISION=5)

    matched = set(gdf["zip"])
    size_mb = OUT.stat().st_size / 1e6
    print(f"written: {OUT}  polygons={len(gdf)}  size={size_mb:.2f} MB")
    missing = serving - matched
    print(f"join alignment: {len(matched)}/{len(serving)} serving ZIPs have a polygon; "
          f"missing={len(missing)}")
    if missing:
        print("  sample missing:", sorted(missing)[:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
