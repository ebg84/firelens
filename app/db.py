"""Read-only DuckDB access + startup manifest validation.

`data/manifest.json` is the pipeline->app contract (locked arch #10). The app
validates the live DB against it at startup and FAILS LOUD on any mismatch, so a
data/app drift can never serve silently. The DB is a generated artifact
(prep/build_duckdb.py); this module never writes to it.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
DUCKDB_PATH = REPO_ROOT / "firelens.duckdb"
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"

# Canonical display order for served metrics (the contract decides WHICH are
# served; this only decides the order we present them). Pending metrics
# (vpd/cdd/dry_wind_days) are intentionally absent — B1.
METRIC_ORDER = ["fwi", "season_length", "dc_pctile"]

# Era labels (CLAUDE.md #6: baseline 1980-2000 vs 2010-present).
BASELINE_ERA = "1980-2000"
RECENT_ERA = "2010-present"


class ManifestMismatch(RuntimeError):
    """Raised when the live DB diverges from the data/manifest.json contract."""


_con: duckdb.DuckDBPyConnection | None = None
_manifest: dict | None = None


def connect() -> duckdb.DuckDBPyConnection:
    """Single process-wide read-only connection; per-query cursors give thread safety."""
    global _con
    if _con is None:
        if not DUCKDB_PATH.exists():
            raise ManifestMismatch(
                f"firelens.duckdb not found at {DUCKDB_PATH}. Run `python prep/build_duckdb.py`."
            )
        _con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    return _con


def load_manifest() -> dict:
    global _manifest
    if _manifest is None:
        if not MANIFEST_PATH.exists():
            raise ManifestMismatch(f"manifest not found at {MANIFEST_PATH}")
        _manifest = json.loads(MANIFEST_PATH.read_text())
    return _manifest


def served_metrics() -> list[str]:
    """Served metrics from the contract, in canonical display order."""
    declared = set(load_manifest()["served_metrics"])
    ordered = [m for m in METRIC_ORDER if m in declared]
    # Surface anything declared-served that we don't have a display order for,
    # rather than silently dropping it.
    return ordered + sorted(declared - set(ordered))


def query(sql: str, params: tuple | list = ()) -> list[tuple]:
    return connect().cursor().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple | list = ()):
    return connect().cursor().execute(sql, params).fetchone()


def validate_contract() -> dict:
    """Fail loud if the live DB does not match the manifest. Returns a summary on success."""
    con = connect()
    mf = load_manifest()
    db_tables = {
        r[0] for r in con.execute("select table_name from information_schema.tables").fetchall()
    }
    problems: list[str] = []
    for tname, spec in mf["tables"].items():
        if tname not in db_tables:
            problems.append(f"manifest table '{tname}' missing from DB")
            continue
        db_cols = {r[0] for r in con.execute(f'describe "{tname}"').fetchall()}
        want = set(spec["columns"])
        if db_cols != want:
            problems.append(
                f"table '{tname}' column mismatch: "
                f"only-in-manifest={sorted(want - db_cols)} only-in-db={sorted(db_cols - want)}"
            )
        n = con.execute(f'select count(*) from "{tname}"').fetchone()[0]
        if n != spec["rows"]:
            problems.append(f"table '{tname}' rowcount {n} != manifest {spec['rows']}")
    if problems:
        raise ManifestMismatch(
            "DB<->manifest contract violations:\n  - " + "\n  - ".join(problems)
        )
    return {
        "tables_validated": len(mf["tables"]),
        "served_metrics": served_metrics(),
        "git_hash": mf["build"]["git_hash"],
    }
