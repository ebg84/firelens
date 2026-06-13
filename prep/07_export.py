"""prep/07_export.py — gated serving-layer export (Module 7, SPINE-NOW).

Refuses to write on a red gate (the spine-now suite). Writes the repo's data/ from
interim tables, restricted to in-CA served cells, plus data/manifest.json (the
pipeline<->app contract, F6). Idempotent: every run overwrites cleanly, so tomorrow's
harvest folds in via a 05_aggregates rerun + a re-export — no append, no drift.

Ships: cell_meta, zip_meta, zip_cell_map, annual_metrics (in-CA), pctile_lut (in-CA),
zip_trends (fwi/season_length/dc_pctile), fire_events. Pending-flagged in the manifest:
vpd, cdd (Lane A harvest), dry_wind_days (wind ladder).

Run:  python prep/07_export.py
"""
import datetime as dt
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb

from prep import metrics, paths

DATA = paths.REPO_ROOT / "data"
GATE_IGNORE = ["tests/prep/test_dailies.py", "tests/prep/test_export.py"]
PENDING = {
    "vpd": {"lane": "Lane A CDS harvest (t_max + td_mean) -> 05_aggregates rerun",
            "blocked_on": "harvest"},
    "cdd": {"lane": "Lane A CDS harvest (precip) -> 05 rerun; precip accumulation-day check pending",
            "blocked_on": "harvest"},
    "dry_wind_days": {"lane": "wind ladder (CDS daily-stats wind upstream issue; forum tripwire)",
                      "blocked_on": "wind"},
}


def gate():
    """Spine-now gate: the whole suite minus the harvest-pending dailies gate and the
    post-export gate. Refuse the export if red."""
    cmd = [sys.executable, "-m", "pytest", "tests/prep/", "-q"]
    for ig in GATE_IGNORE:
        cmd += ["--ignore", ig]
    r = subprocess.run(cmd, cwd=paths.REPO_ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"GATE RED — export refused.\n{r.stdout[-1500:]}")
    print("gate green (spine-now suite)", flush=True)


def _git_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=paths.REPO_ROOT, text=True).strip()
    except Exception:
        return "unknown"


def export():
    gate()
    DATA.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    I = paths.INTERIM
    cm = I / "cell_meta.parquet"  # the in-CA served cell set

    # table -> SQL selecting what ships (restricted to in-CA cells where relevant)
    tables = {
        "cell_meta": f"select * from '{cm}'",
        "zip_meta": f"select * from '{I/'zip_meta.parquet'}'",
        "zip_cell_map": f"select * from '{I/'zip_cell_map.parquet'}'",
        "annual_metrics": f"select * from '{I/'annual_metrics.parquet'}' "
                          f"where cell_id in (select cell_id from '{cm}')",
        "pctile_lut": f"select * from '{I/'pctile_lut.parquet'}' "
                      f"where cell_id in (select cell_id from '{cm}')",
        "zip_trends": f"select * from '{I/'zip_trends.parquet'}'",
        "fire_events": f"select * from '{I/'fire_events.parquet'}'",
    }
    manifest_tables = {}
    for name, q in tables.items():
        out = DATA / f"{name}.parquet"
        con.execute(f"copy ({q}) to '{out}' (format parquet)")
        info = con.execute(f"select count(*) c from '{out}'").fetchone()
        cols = con.execute(f"select * from '{out}' limit 0").df().columns.tolist()
        manifest_tables[name] = {"rows": info[0], "columns": cols}
        print(f"  {name}: {info[0]:,} rows", flush=True)

    # "served_metrics" = metrics ACTUALLY LIVE in the export (present in zip_trends),
    # not every registry served=True — vpd/cdd/dry_wind_days are served-but-pending-data
    # and belong only in pending_metrics (no metric appears in both).
    live = sorted({r[0] for r in con.execute(
        f"select distinct metric from '{DATA/'zip_trends.parquet'}'").fetchall()})
    manifest = {
        "build": {"git_hash": _git_hash(),
                  "built_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "spine_now": True},
        "tables": manifest_tables,
        "served_metrics": live,
        "pending_metrics": PENDING,
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # size budget
    total = sum(p.stat().st_size for p in DATA.rglob("*") if p.is_file())
    assert total < 100 * 1024 * 1024, f"data/ is {total/1e6:.1f} MB (> 100 MB budget)"
    print(f"\nexported {len(manifest_tables)} tables, manifest written, "
          f"data/ = {total/1e6:.2f} MB", flush=True)
    print(f"served: {manifest['served_metrics']}  | pending: {list(PENDING)}", flush=True)


if __name__ == "__main__":
    export()
