"""prep/audit_integrity.py — READ-ONLY integration-integrity audit.

Reports the metric × spatial × temporal × granularity × grain × vintage × state table,
the unguarded-risk list, and any drift of data/ from the committed baseline. Mutates
NOTHING (no served-layer writes, no promotions). Safe to run every loop cycle.

Run:  python prep/audit_integrity.py
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb

from prep import paths

D = paths.REPO_ROOT / "data"
I = paths.INTERIM

# The domain contract each metric/layer SHOULD carry. The audit flags where the
# manifest does not yet declare it (that gap IS the unguarded risk).
DOMAIN = [
    # name, spatial, canon?, temporal range, granularity, grain, vintage, state
    ("fwi", "zip(1801)+cell(824)", True, "1940–2026", "era-trend / annual / weekly-pctile", "ZIP via zip_cell_map", "GEFF-ERA5", "served"),
    ("season_length", "zip(1801)+cell(824)", True, "1940–2026", "era-trend / annual", "ZIP via zip_cell_map", "GEFF-ERA5", "served"),
    ("dc_pctile", "zip(1801)+cell(824)", True, "1940–2026", "era-trend / weekly-pctile", "ZIP via zip_cell_map", "GEFF-ERA5", "served"),
    ("fire_events", "point→cell(556)", False, "1992–2025", "point-events", "per-fire", "FPA-FOD 92–20 + FRAP 21+", "served"),
    ("vpd", "zip when landed", True, "1980–2026", "daily→annual", "ZIP", "ERA5 (CDS)", "pending:harvest"),
    ("cdd", "zip when landed", True, "1980–2026", "daily→annual", "ZIP", "ERA5 (CDS)", "pending:harvest"),
    ("dry_wind_days", "zip when landed", True, "—", "daily→annual", "ZIP", "ERA5 (wind)", "pending:wind"),
    ("nri (consequence)", "zip(1693)", False, "2025 snapshot", "STATIC", "ZIP (94%)", "FEMA NRI v1.20", "additive:interim"),
    ("priority_matrix", "zip(1693)", False, "static", "STATIC", "ZIP (94%)", "FWI-era × NRI-2025", "additive:interim"),
    ("firms_density", "—", False, "2000–present", "all-time density", "hex/cell", "(not staged)", "not-started"),
    ("fuel_context", "—", False, "current cycle", "STATIC", "ZIP/cell", "(not staged)", "not-started"),
]


def main():
    con = duckdb.connect()
    canon = con.execute(f"select count(distinct zip) from '{D/'zip_meta.parquet'}'").fetchone()[0]
    man = json.load(open(D / "manifest.json"))
    print("=" * 90)
    print(f"INTEGRATION-INTEGRITY AUDIT (read-only). Canonical ZCTA set = {canon}")
    print("=" * 90)
    print(f"{'metric/layer':20} {'spatial':22} {'temporal range':14} {'granularity':32} {'state':16}")
    for r in DOMAIN:
        print(f"{r[0]:20} {r[1]:22} {r[3]:14} {r[4]:32} {r[7]:16}")

    risks = []
    # 1. manifest declares state/lane but NOT spatial/range/granularity/vintage
    sample = man.get("tables", {}).get("zip_trends", {})
    if "granularity" not in sample and "temporal_range" not in man.get("metric_domains", {}):
        risks.append("[ROOT] manifest declares served/pending+lane but NOT per-metric "
                     "spatial_key/range/granularity/grain/vintage → no consumer contract to "
                     "refuse out-of-domain requests; every risk below stems from this.")
    # 2. NRI/matrix spatial mismatch vs canonical
    for t in ["nri_zip", "zip_priority_matrix"]:
        p = I / f"{t}.parquet"
        if p.exists():
            n = con.execute(f"select count(distinct zip) from '{p}'").fetchone()[0]
            if n != canon:
                risks.append(f"[SPATIAL] {t}: {n} ZIPs ≠ canonical {canon} → {canon-n} ZIPs have no "
                             f"value (104 non-residential + 4 F8); consumer MUST omit-with-note.")
    # 3-5 domain-shape traps
    risks.append("[TEMPORAL] nri/priority_matrix are a 2025 SNAPSHOT (STATIC) → must never be "
                 "plotted on a time axis or animated over years.")
    risks.append("[TEMPORAL] pctile_lut is a CLIMATOLOGY (iso_week, all years pooled) → no single "
                 "year; treating a percentile as year-specific misrepresents it.")
    risks.append("[TEMPORAL] zip_trends is an ERA COMPARISON (baseline vs recent, 2 points) → "
                 "plotting it as a continuous annual line implies a series that lives only in "
                 "annual_metrics (cell-grained), not here.")
    risks.append("[SPATIAL] annual_metrics & pctile_lut are CELL-grained (824), not ZIP → consumer "
                 "MUST aggregate via zip_cell_map at query time; mapping cell↔ZIP directly is wrong.")
    risks.append("[CROSS] NRI×FWI is a CROSS-SECTIONAL correlation across ZIPs, not temporal → must "
                 "not be presented as 'fire weather over time vs NRI'.")
    # 6. FIRMS/LANDFIRE not declared in manifest at all
    declared = set(man.get("served_metrics", [])) | set(man.get("pending_metrics", {}))
    for layer in ["firms_density", "fuel_context"]:
        if layer not in declared:
            risks.append(f"[CONTRACT] {layer} is not declared in the manifest at all → pending "
                         f"layers must be declared so a consumer can show 'data pending', not break.")

    print("\nUNGUARDED-RISK LIST (no consumer exists yet; contract is incomplete):")
    for i, r in enumerate(risks, 1):
        print(f"  {i}. {r}")

    # baseline drift (overnight must NOT mutate the served layer)
    drift = subprocess.run(["git", "diff", "--quiet", "--", "data/"], cwd=paths.REPO_ROOT).returncode
    tubbs = con.execute(f"select round(fwi_pctile,4) from '{D/'fire_events.parquet'}' "
                        f"where upper(name)='TUBBS' and year(ign_date)=2017").fetchone()[0]
    print(f"\nBASELINE: data/ drift from committed = {'CLEAN' if drift==0 else 'DRIFTED ***'} | "
          f"Tubbs anchor = {tubbs} ({'OK' if tubbs>=0.90 else 'REGRESSED ***'})")
    print("=" * 90)


if __name__ == "__main__":
    main()
