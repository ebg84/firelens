"""prep/fuel.py — LANDFIRE FBFM40 fuel composition per ZIP (importable; Module 8c).

Raster zonal join: read the code→class mapping from the shipped .vat (never hardcode),
mask non-burnable (NB*, codes 91–99) BEFORE computing burnable composition so developed
ZIPs aren't diluted, but report non_burnable_frac as its own meaningful field. The ZCTA
overlay MUST be in the raster's own CRS (CRS mismatch is the #1 zonal-stats bug).
"""
import pyogrio
from rasterstats import zonal_stats

# FBFM40 string prefix -> digestible group (the standard FBFM40 fuel families)
PREFIX = {"NB": "non_burnable", "GR": "grass", "GS": "grass_shrub", "SH": "shrub",
          "TU": "timber_understory", "TL": "timber_litter", "SB": "slash_blowdown"}
NONBURN = "non_burnable"
BURN_GROUPS = ["grass", "grass_shrub", "shrub", "timber_understory",
               "timber_litter", "slash_blowdown"]


def fbfm_groups(vat_dbf_path):
    """Read the .vat attribute table -> {pixel value: group}, grouping by the FBFM40
    string prefix. NOT hardcoded — comes from the shipped table."""
    t = pyogrio.read_dataframe(vat_dbf_path, read_geometry=False)[["Value", "FBFM40"]]
    t["group"] = t["FBFM40"].str.extract(r"^([A-Za-z]+)")[0].map(PREFIX)
    return dict(zip(t["Value"].astype(int), t["group"]))


def composition(zcta_gdf_in_raster_crs, raster_path, value_group, nodata=-9999):
    """Per-ZIP fuel composition. zcta_gdf MUST already be in the raster CRS.
    burnable group fractions are OF BURNABLE pixels (non-burnable masked);
    non_burnable_frac and burnable_frac are OF TOTAL."""
    stats = zonal_stats(zcta_gdf_in_raster_crs, raster_path, categorical=True,
                        nodata=nodata, all_touched=False)
    rows = []
    for zip_, cats in zip(zcta_gdf_in_raster_crs["zip"], stats):
        grp = {}
        for v, c in (cats or {}).items():
            g = value_group.get(int(v))
            if g:
                grp[g] = grp.get(g, 0) + int(c)
        total = sum(grp.values())
        nonb = grp.get(NONBURN, 0)
        burn = total - nonb
        row = {"zip": zip_, "total_px": int(total),
               "non_burnable_frac": (nonb / total) if total else None,
               "burnable_frac": (burn / total) if total else None}
        for g in BURN_GROUPS:
            # NULL (not 0.0) where nothing burnable: composition is UNDEFINED, not a
            # measured zero — a zero-burnable ZIP has no burnable pixels to compose.
            row[g + "_frac"] = (grp.get(g, 0) / burn) if burn else None
        row["dominant_class"] = (max(BURN_GROUPS, key=lambda g: grp.get(g, 0))
                                 if burn else "non_burnable")
        rows.append(row)
    import pandas as pd
    return pd.DataFrame(rows)
