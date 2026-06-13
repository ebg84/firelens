"""prep/verify_ca_footprint.py — geographic FOOTPRINT correctness (read-only).

Distinct from the join-resolution sweep: this confirms the data actually maps to CALIFORNIA
(identity, county, coordinate bounds, raster placement, cell coverage, named-ZIP spot checks),
not just that the joins are internally coherent. Reads committed data/ + the LANDFIRE raster.
"""
import glob
import os
import sys

import duckdb

D = "/Users/ethangray/claudebuild/firelens/data"
RAW = os.path.expanduser("~/claudebuild/firelens-data/raw")
CA = dict(lat_lo=32.5, lat_hi=42.0, lon_lo=-124.5, lon_hi=-114.1)
c = duckdb.connect()
q = lambda s: c.execute(s).fetchall()
q1 = lambda s: c.execute(s).fetchone()
results = {}


def line(): print("=" * 72)


# CHECK 1 — ZCTA identity
line(); print("CHECK 1 — ZCTA IDENTITY (CA 90001–96162, prefix 90–96)")
zips = [r[0] for r in q(f"select zip from '{D}/zip_meta.parquet'")]
bad_prefix = [z for z in zips if z[:2] not in {'90', '91', '92', '93', '94', '95', '96'}]
bad_range = [z for z in zips if not (90001 <= int(z) <= 96162)]
print(f"  served ZCTAs: {len(zips)}   min={min(zips)}  max={max(zips)}")
print(f"  outside prefix 90–96: {len(bad_prefix)} {bad_prefix[:20]}")
print(f"  outside numeric 90001–96162: {len(bad_range)} {sorted(bad_range)[:20]}")
results['1 ZCTA identity'] = not bad_range and not bad_prefix

# CHECK 2 — county FIPS
line(); print("CHECK 2 — COUNTY FIPS (CA state 06, 06001–06115)")
ok2 = True
for tbl in ['zip_meta', 'cell_meta']:
    fips = [str(r[0]) for r in q(f"select distinct county_fips from '{D}/{tbl}.parquet' where county_fips is not null")]
    non06 = [f for f in fips if not f.startswith('06')]
    outrange = [f for f in fips if f.startswith('06') and not (1 <= int(f[2:]) <= 115)]
    ok2 = ok2 and not non06 and not outrange
    print(f"  {tbl}: {len(fips)} counties; range {min(fips)}–{max(fips)}; non-06: {non06[:10]}; out-of-range: {outrange[:10]}")
results['2 county FIPS'] = ok2

# CHECK 3 — coordinate bounds
line(); print(f"CHECK 3 — COORDINATE BOUNDS (lat {CA['lat_lo']}–{CA['lat_hi']}, lon {CA['lon_lo']}–{CA['lon_hi']})")
ok3 = True
for tbl in ['zip_meta', 'cell_meta']:
    la_lo, la_hi, lo_lo, lo_hi = q1(f"select min(lat),max(lat),min(lon),max(lon) from '{D}/{tbl}.parquet'")
    out = q1(f"select count(*) from '{D}/{tbl}.parquet' where lat<{CA['lat_lo']} or lat>{CA['lat_hi']} "
             f"or lon<{CA['lon_lo']} or lon>{CA['lon_hi']}")[0]
    ok3 = ok3 and out == 0
    print(f"  {tbl}: lat [{la_lo:.3f}, {la_hi:.3f}]  lon [{lo_lo:.3f}, {lo_hi:.3f}]  outside-bbox: {out}")
results['3 coordinate bounds'] = ok3

# CHECK 4 — fuel raster placement
line(); print("CHECK 4 — FUEL RASTER PLACEMENT (CA-Albers extent overlays CA)")
try:
    import rasterio
    from rasterio.warp import transform_bounds
    tif = glob.glob(f"{RAW}/landfire/*.tif")[0]
    with rasterio.open(tif) as r:
        b = r.bounds
        wlon_lo, wlat_lo, wlon_hi, wlat_hi = transform_bounds(r.crs, "EPSG:4326", *b)
    print(f"  raster CRS: {r.crs.to_string()[:46]}...")
    print(f"  raster bounds -> WGS84: lat [{wlat_lo:.3f}, {wlat_hi:.3f}]  lon [{wlon_lo:.3f}, {wlon_hi:.3f}]")
    overlaps = (wlat_lo <= CA['lat_hi'] and wlat_hi >= CA['lat_lo']
                and wlon_lo <= CA['lon_hi'] and wlon_hi >= CA['lon_lo'])
    # spot-check a known forested CA ZIP has non-empty burnable fuel
    spot = q1(f"select burnable_frac, dominant_class, total_px from '{D}/fuel_context.parquet' where zip='96001'")
    print(f"  raster overlaps CA bbox: {overlaps}")
    print(f"  fuel spot 96001 (Redding): burnable_frac={spot[0]:.3f} dominant={spot[1]} total_px={spot[2]}")
    results['4 fuel raster placement'] = overlaps and spot[2] > 0 and spot[0] > 0
except Exception as e:
    print(f"  ERROR: {e}")
    results['4 fuel raster placement'] = False

# CHECK 5 — cell grid coverage
line(); print("CHECK 5 — CELL GRID COVERAGE (824 span CA; 92 ZIP-less are in-state buffer)")
zcm = {r[0] for r in q(f"select distinct cell_id from '{D}/zip_cell_map.parquet'")}
allc = {r[0] for r in q(f"select cell_id from '{D}/cell_meta.parquet'")}
orph = allc - zcm
ol = ",".join(str(o) for o in orph)
o_out = q1(f"select count(*) from '{D}/cell_meta.parquet' where cell_id in ({ol}) and "
           f"(lat<{CA['lat_lo']} or lat>{CA['lat_hi']} or lon<{CA['lon_lo']} or lon>{CA['lon_hi']})")[0]
obb = q1(f"select min(lat),max(lat),min(lon),max(lon) from '{D}/cell_meta.parquet' where cell_id in ({ol})")
print(f"  cells: {len(allc)}; ZIP-serving: {len(zcm)}; ZIP-less (orphan): {len(orph)}")
print(f"  orphan-cell bbox: lat [{obb[0]:.3f}, {obb[1]:.3f}]  lon [{obb[2]:.3f}, {obb[3]:.3f}]  outside CA bbox: {o_out}")
results['5 cell grid coverage'] = (len(allc) == 824 and o_out == 0)

# CHECK 6 — named-ZIP spot check
line(); print("CHECK 6 — NAMED-ZIP SPOT CHECK")
expect = {'90001': ('Los Angeles', '06037', 33.97, -118.25),
          '94102': ('San Francisco', '06075', 37.78, -122.42),
          '96001': ('Redding', '06089', 40.58, -122.39)}
ok6 = True
for z, (name, fips, elat, elon) in expect.items():
    r = q1(f"select lat,lon,county_fips from '{D}/zip_meta.parquet' where zip='{z}'")
    if not r:
        print(f"  {z} {name}: ABSENT"); ok6 = False; continue
    lat, lon, cf = r
    t = q1(f"select recent, pct_change from '{D}/zip_trends.parquet' where zip='{z}' and metric='fwi'")
    near = abs(lat - elat) < 0.5 and abs(lon - elon) < 0.5
    good = near and cf == fips
    ok6 = ok6 and good
    fwi = f"fwi_recent={t[0]:.2f} Δ={t[1]:+.1%}" if t else "no-trend"
    print(f"  {z} {name:14s}: lat={lat:.3f} lon={lon:.3f} (exp ~{elat},{elon}) "
          f"county={cf} (exp {fips}) {fwi}  {'OK' if good else 'FLAG'}")
results['6 named-ZIP spot check'] = ok6

line(); print("FOOTPRINT VERDICT")
for k, v in results.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
print(f"\n  {sum(results.values())}/{len(results)} checks PASS")
