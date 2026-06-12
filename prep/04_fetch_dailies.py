"""prep/04_fetch_dailies.py — Open-Meteo daily variables over the CA cell set.

PROBE STAGE ONLY (this commit): a single-cell end-to-end probe that retires the
Open-Meteo [ASSUMPTION]s before the bulk fetch — actual daily variable names
(especially the VPD humidity ingredient dew_point_2m_mean), the units echo,
requested-vs-returned coordinates under cell_selection=nearest, and the served
date span. The bulk fetch over the 732 ZIP-serving cells is added only after the
probe report is reviewed (UNITS GUARD: wind_speed_unit=ms).

Run:  python prep/04_fetch_dailies.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import json

import requests

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "dew_point_2m_mean",
              "wind_speed_10m_max", "precipitation_sum"]


def _get(url, params):
    r = requests.get(url, params=params, timeout=60)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text[:300]}


def probe(lat=38.5, lon=-122.5, start="2017-10-01", end="2017-10-10"):
    print("=" * 70)
    print(f"OPEN-METEO ARCHIVE PROBE — requested ({lat}, {lon}), {start}..{end}")
    print("=" * 70)

    # 1) full daily request including dew_point_2m_mean, wind in m/s
    p = dict(latitude=lat, longitude=lon, start_date=start, end_date=end,
             daily=",".join(DAILY_VARS), wind_speed_unit="ms",
             timezone="GMT", cell_selection="nearest")
    code, j = _get(ARCHIVE, p)
    print(f"\n[1] daily incl dew_point_2m_mean  -> HTTP {code}")
    if j.get("error"):
        print(f"    ERROR: {j.get('reason')}")
    else:
        print(f"    returned coord : ({j.get('latitude')}, {j.get('longitude')})  "
              f"elev {j.get('elevation')}  (cell_selection=nearest)")
        du = j.get("daily_units", {})
        print(f"    daily_units    : {du}")
        d = j.get("daily", {})
        print(f"    daily keys     : {list(d.keys())}")
        t = d.get("time", [])
        print(f"    date span      : {t[0] if t else '-'} .. {t[-1] if t else '-'}  ({len(t)} days)")
        if "time" in d and "2017-10-08" in t:
            i = t.index("2017-10-08")
            row = {k: v[i] for k, v in d.items() if k != "time"}
            print(f"    2017-10-08     : {row}")
        missing = [v for v in DAILY_VARS if v not in d]
        print(f"    requested-but-absent daily vars: {missing or 'none'}")

    # 2) confirm the humidity ingredient is reachable hourly if daily form is absent
    ph = dict(latitude=lat, longitude=lon, start_date="2017-10-08", end_date="2017-10-08",
              hourly="dew_point_2m,relative_humidity_2m,temperature_2m", timezone="GMT")
    code2, j2 = _get(ARCHIVE, ph)
    print(f"\n[2] hourly humidity fallback check -> HTTP {code2}")
    if j2.get("error"):
        print(f"    ERROR: {j2.get('reason')}")
    else:
        hu = j2.get("hourly_units", {})
        hk = list(j2.get("hourly", {}).keys())
        print(f"    hourly keys    : {hk}")
        print(f"    hourly_units   : {hu}")
    print("=" * 70)
    print("BULK FETCH NOT RUN — awaiting probe review.")
    print("=" * 70)


if __name__ == "__main__":
    probe()
