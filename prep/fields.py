"""Canonical source->name mappings and the spatial key (the one place field
spellings and the cell_id convention live; DATA.md Part C F1/F3).

Longitude convention (the F1 trap): GEFF NetCDFs store east-positive longitudes
in 0-360 (e.g. 235.0 == 125 W). DATA.md's cell_id formula,
    cell_id = round(lat*4)*10000 + round((lon + 360)*4),
was written for signed west-negative longitudes (-125), where (lon + 360) lands
the western US in 235-246. Feeding raw 0-360 values straight in double-shifts the
term and silently mis-registers every cell. ALWAYS pass longitude through
to_signed_lon() first.
"""
import numpy as np

# GEFF-ERA5 (S1) variable names, verified from the live files 2026-06-12.
GEFF_VARS = {"fwinx": "fwi", "ercnfdr": "erc", "drtcode": "dc"}


def to_signed_lon(lon):
    """Map east-positive 0-360 longitude to signed -180..180 (west negative).

    Idempotent on values already in -180..180. Works on scalars and arrays.
    """
    return ((np.asarray(lon, dtype="float64") + 180.0) % 360.0) - 180.0


def cell_id(lat, lon_signed):
    """0.25-deg lattice key (DATA.md Part B 1.0).

    lon_signed MUST be signed west-negative (pass file longitudes through
    to_signed_lon first). Returns int (scalar) or int array.
    """
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon_signed, dtype="float64")
    cid = (np.round(lat * 4).astype("int64") * 10000
           + np.round((lon + 360.0) * 4).astype("int64"))
    return cid.item() if cid.ndim == 0 else cid


def cell_to_latlon(cid):
    """Inverse of cell_id: recover (lat, signed_lon) cell-center coordinates."""
    cid = np.asarray(cid, dtype="int64")
    lat = (cid // 10000) / 4.0
    lon = (cid % 10000) / 4.0 - 360.0
    if lat.ndim == 0:
        return lat.item(), lon.item()
    return lat, lon
