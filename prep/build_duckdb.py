"""prep/build_duckdb.py — build the READ-ONLY DuckDB serving database from the committed
serving parquet. The parquet stays the source of truth; this DB is a GENERATED artifact,
regenerated from data/, never written to by consumers.

INVARIANT: reproducible from committed inputs alone. Inputs are EXACTLY data/*.parquet +
data/manifest.json (all committed at HEAD) — no interim/ or gitignored dependency. A fresh
clone + `python prep/build_duckdb.py` rebuilds an identical DB. The .duckdb binary is
gitignored; this builder is committed.

Objects built:
  - 10 base tables: 1:1 mirror of the committed parquet (types + NULLs preserved).
  - cell_annual VIEW: the 824-cell annual field joined to cell lat/lon/county (the
    non-blocky cell-field map UX — render at native 0.25 deg grain, not flat ZIP blocks).
  - zip_serving VIEW: one row per CANONICAL 1,801 ZCTA (NOT NRI's 1,693) — the per-ZIP
    CURRENT/SNAPSHOT serving row. Era-comparison + static layers only; NO time series.
  - metric_domains TABLE: the manifest coherence contract (grain/range/granularity/vintage/
    state) carried INTO the DB so a consumer reads each metric's grain from the DB itself.

Idempotent: drops and rebuilds the whole file from immutable source — content-equal every run.
Run:  python prep/build_duckdb.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb

from prep import paths

DATA = paths.REPO_ROOT / "data"
DB_PATH = paths.REPO_ROOT / "firelens.duckdb"

# the 10 committed serving tables (mirrored 1:1)
BASE_TABLES = ["cell_meta", "zip_meta", "zip_cell_map", "annual_metrics", "pctile_lut",
               "zip_trends", "fire_events", "nri_zip", "zip_priority_matrix", "fuel_context"]
SERVED_SPINE_METRICS = ["fwi", "season_length", "dc_pctile"]   # the zip_trends pivot
FUEL_COMPOSITION = ["grass_frac", "grass_shrub_frac", "shrub_frac",
                    "timber_understory_frac", "timber_litter_frac", "slash_blowdown_frac"]


def _domains_rows(manifest):
    """Flatten manifest.metric_domains into uniform rows (a coherence contract the DB carries)."""
    rows = []
    for metric, d in manifest.get("metric_domains", {}).items():
        rows.append({
            "metric": metric, "state": d.get("state"),
            "spatial_grain": d.get("spatial_grain"), "join_key": d.get("join_key"),
            "temporal_range": d.get("temporal_range"),
            "temporal_granularity": d.get("temporal_granularity"),
            "vintage": d.get("vintage"), "blocked_on": d.get("blocked_on"),
            "note": d.get("note"), "tables_json": json.dumps(d.get("tables", []))})
    return rows


def build(db_path=DB_PATH, data_dir=DATA):
    """Build the serving DB from data_dir's committed parquet. Returns the db path."""
    db_path = pathlib.Path(db_path)
    if db_path.exists():
        db_path.unlink()                      # idempotent: rebuild whole file from source
    con = duckdb.connect(str(db_path))

    # 1. base tables — 1:1 from parquet (read_parquet preserves dtypes + true NULLs)
    for t in BASE_TABLES:
        con.execute(f"create table {t} as select * from read_parquet('{data_dir}/{t}.parquet')")

    # 2. metric_domains contract table (carried from the manifest)
    manifest = json.loads((data_dir / "manifest.json").read_text())
    import pandas as pd
    dom = pd.DataFrame(_domains_rows(manifest))
    con.register("dom_df", dom)
    con.execute("create table metric_domains as select * from dom_df")
    con.unregister("dom_df")

    # 3. cell_annual view — the 824-cell annual field WITH coordinates (native-grain UX)
    con.execute("""
        create view cell_annual as
        select a.cell_id, m.lat, m.lon, m.county_fips, a.year,
               a.fwi_mean, a.fwi_max, a.extreme_days, a.season_len, a.dc_max, a.erc_mean
        from annual_metrics a join cell_meta m using (cell_id)
    """)

    # 4. zip_serving wide view — one row per canonical 1,801 ZCTA, LEFT JOINs from the spine
    pivot = ",\n".join(
        f"max(baseline) filter (where metric='{m}') as {m}_baseline,\n"
        f"max(recent) filter (where metric='{m}') as {m}_recent,\n"
        f"max(pct_change) filter (where metric='{m}') as {m}_pct_change,\n"
        f"max(freq_ratio) filter (where metric='{m}') as {m}_freq_ratio,\n"
        f"max(robust) filter (where metric='{m}') as {m}_robust"
        for m in SERVED_SPINE_METRICS)
    con.execute(f"""
        create view zip_serving as
        with trends as (select zip, {pivot} from zip_trends group by zip)
        select
            z.zip, z.lat, z.lon, z.county_fips,
            {", ".join(f"t.{m}_{s}" for m in SERVED_SPINE_METRICS
                       for s in ["baseline","recent","pct_change","freq_ratio","robust"])},
            n.n_tracts as nri_n_tracts, n.wfir_risks, n.wfir_afreq, n.wfir_ealt,
            pm.quadrant,
            f.total_px as fuel_total_px, f.burnable_frac, f.non_burnable_frac,
            {", ".join(f"f.{c}" for c in FUEL_COMPOSITION)},
            f.dominant_class
        from zip_meta z
        left join trends t              using (zip)
        left join nri_zip n             using (zip)
        left join zip_priority_matrix pm using (zip)
        left join fuel_context f        using (zip)
    """)

    # 5. coherence/NULL-provenance comments carried INTO the DB
    con.execute("comment on view zip_serving is "
                "'One row per CANONICAL 1,801 ZCTA (a CURRENT/SNAPSHOT serving row, NOT a time "
                "series). Spine metrics are ERA comparisons (baseline 1980-2000 vs recent "
                "2010+) underlain by 824 cells; NRI/matrix are 2025-static; fuel is static. "
                "The 1940-2026 annual series lives in cell_annual; fire events in fire_events. "
                "NULL SEMANTICS: wfir_*/quadrant NULL = ZIP not in NRI 1,693 (108 non-residential/F8) "
                "-> ABSENT, not zero risk. Fuel composition NULL = zero-burnable ZIP (undefined), "
                "DISTINCT from burnable_frac=0 (a real measured zero).'")
    con.execute("comment on column zip_serving.wfir_risks is "
                "'NULL = ZIP absent from NRI 1,693 (not zero risk). FEMA NRI 2025 static.'")
    con.execute("comment on column zip_serving.shrub_frac is "
                "'NULL where burnable_frac=0 (composition undefined, not a measured zero).'")
    con.execute("comment on table metric_domains is "
                "'Coherence contract from data/manifest.json: each metric grain/range/state. "
                "Consumers read grain HERE; never assume a uniform 1,801 or a finer-than-declared axis.'")
    con.close()
    return db_path


# ---- diff-validation: DB must equal source parquet (shared by the gate test) -------------

def diff_against_source(db_path=DB_PATH, data_dir=DATA):
    """Return a list of drift strings (empty == DB faithfully equals source). Checks row
    counts, dtypes (coercion), NULL counts per column (the 108/12/all-NULL), numeric ranges,
    and ZIP key format. A weak diff is theater; this is column-level."""
    con = duckdb.connect(str(db_path), read_only=True)
    drifts = []
    for t in BASE_TABLES:
        src = f"read_parquet('{data_dir}/{t}.parquet')"
        # row count
        dn = con.execute(f"select count(*) from {t}").fetchone()[0]
        sn = con.execute(f"select count(*) from {src}").fetchone()[0]
        if dn != sn:
            drifts.append(f"{t}: rowcount DB {dn} != source {sn}")
        # per-column dtype + null-count + numeric range
        db_types = dict(con.execute(f"describe {t}").df()[["column_name", "column_type"]].values)
        src_types = dict(con.execute(f"describe select * from {src}").df()[["column_name", "column_type"]].values)
        if list(db_types) != list(src_types):
            drifts.append(f"{t}: column set/order DB {list(db_types)} != source {list(src_types)}")
            continue
        for col, dt in db_types.items():
            if dt != src_types[col]:
                drifts.append(f"{t}.{col}: dtype DB {dt} != source {src_types[col]} (coercion)")
            dnull = con.execute(f"select count(*) - count({col}) from {t}").fetchone()[0]
            snull = con.execute(f"select count(*) - count({col}) from {src}").fetchone()[0]
            if dnull != snull:
                drifts.append(f"{t}.{col}: NULL count DB {dnull} != source {snull}")
            if any(k in dt.upper() for k in ("INT", "DOUBLE", "FLOAT", "DECIMAL")):
                drange = con.execute(f"select min({col}), max({col}) from {t}").fetchone()
                srange = con.execute(f"select min({col}), max({col}) from {src}").fetchone()
                if drange != srange:
                    drifts.append(f"{t}.{col}: range DB {drange} != source {srange}")
        # ZIP key format (leading-zero / 5-digit preservation)
        if "zip" in db_types:
            bad = con.execute(f"select count(*) from {t} where length(zip) != 5").fetchone()[0]
            if bad:
                drifts.append(f"{t}: {bad} ZIPs not 5-digit (leading-zero coercion)")
            dz = con.execute(f"select count(distinct zip) from {t}").fetchone()[0]
            sz = con.execute(f"select count(distinct zip) from {src}").fetchone()[0]
            if dz != sz:
                drifts.append(f"{t}: distinct-zip DB {dz} != source {sz}")
    con.close()
    return drifts


def all_null_columns(db_path=DB_PATH):
    """Columns that are 100% NULL in source — carried through honestly (never fabricated)."""
    con = duckdb.connect(str(db_path), read_only=True)
    out = []
    for t in BASE_TABLES:
        for col in con.execute(f"describe {t}").df()["column_name"]:
            n, nn = con.execute(f"select count(*), count({col}) from {t}").fetchone()
            if n > 0 and nn == 0:
                out.append(f"{t}.{col}")
    con.close()
    return out


def report():
    db = build()
    print(f"built {db.name}  ({db.stat().st_size/1e6:.1f} MB)\n")

    drifts = diff_against_source(db)
    print(f"DIFF-VALIDATION vs source parquet: {'CLEAN (0 drifts)' if not drifts else f'{len(drifts)} DRIFT(S)'}")
    for d in drifts:
        print(f"  DRIFT: {d}")

    nulls = all_null_columns(db)
    print(f"\nALL-NULL columns carried through (NOT fabricated): {nulls or 'none'}")

    con = duckdb.connect(str(db), read_only=True)
    print("\nzip_serving schema:")
    for c, t in con.execute("describe zip_serving").df()[["column_name", "column_type"]].values:
        print(f"  {c:24s} {t}")

    print("\n3-ZIP sample (timber-heavy / grass-heavy / urban-non-residential):")
    picks = {
        "timber-heavy": con.execute("select zip from zip_serving where dominant_class like 'timber%' "
                                    "and burnable_frac>0.5 order by burnable_frac desc limit 1").fetchone()[0],
        "grass-heavy": con.execute("select zip from zip_serving where dominant_class='grass' "
                                   "and burnable_frac>0.5 order by grass_frac desc limit 1").fetchone()[0],
        "urban/non-resid (NRI-less)": con.execute("select zip from zip_serving where wfir_risks is null "
                                                  "order by non_burnable_frac desc limit 1").fetchone()[0]}
    cols = ("zip, county_fips, fwi_recent, fwi_pct_change, quadrant, wfir_risks, wfir_ealt, "
            "burnable_frac, dominant_class, shrub_frac, timber_litter_frac")
    for label, z in picks.items():
        r = con.execute(f"select {cols} from zip_serving where zip=?", [z]).df().iloc[0]
        print(f"\n  [{label}] {z}:")
        for k, v in r.items():
            print(f"      {k:20s} = {v}")
    con.close()


if __name__ == "__main__":
    report()
