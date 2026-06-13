"""prep/11_promote_additive.py — promote the three additive layers into the committed
serving layer (data/), idempotently.

Why: the wide DuckDB serving view needs NRI, the priority matrix, and fuel composition,
but those were built into interim/ (outside the repo). Promoting them into data/ makes the
serving DB reproducible-from-HEAD (no dependency on the gitignored heavy root).

What it does (idempotent — re-running yields byte-identical data/ + manifest):
  1. Fuel NULL-correctness: composition fractions are NULL (not 0.0) where burnable_frac=0
     (the 12 zero-burnable ZIPs) — composition is UNDEFINED there, not a measured zero. Written
     as TRUE parquet NULLs via DuckDB COPY (pandas NaN would pass IS NULL falsely).
  2. Copies nri_zip, zip_priority_matrix, fuel_context (NULL-fixed) into data/.
  3. Registers them in manifest.tables (rows+columns) and drops the "(interim)" marker from
     each domain's tables list. State stays "additive" (locked by test_domains; promotion is a
     LOCATION change, not a state change).

NOTE — matrix hazard axis: the committed zip_priority_matrix uses fwi_level = recent-era MEAN
FWI. The pending hazard-axis switch (high-percentile-day count, to unify with the Tubbs-tail
headline) will re-sort some ZIPs and RE-EXPORT this table. Committed now as stable; flagged.

Run:  python prep/11_promote_additive.py   (requires the interim root; output is committed)
"""
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb

from prep import paths

DATA = paths.REPO_ROOT / "data"
I = paths.INTERIM
COMPOSITION = ["grass_frac", "grass_shrub_frac", "shrub_frac",
               "timber_understory_frac", "timber_litter_frac", "slash_blowdown_frac"]
# domain key in manifest.metric_domains -> parquet stem in data/
PROMOTE = {"nri": "nri_zip", "priority_matrix": "zip_priority_matrix", "fuel_context": "fuel_context"}


def fix_fuel_nulls(con):
    """Rewrite interim fuel_context with NULL composition where burnable_frac=0, as TRUE
    parquet nulls. Idempotent: CASE re-applies to already-null rows harmlessly."""
    src = I / "fuel_context.parquet"
    others = [c for c in con.execute(f"select * from '{src}' limit 0").df().columns
              if c not in COMPOSITION]
    # NULL composition wherever nothing is burnable: burnable_frac = 0 (covered, all
    # non-burnable) OR burnable_frac IS NULL (total_px=0, no raster coverage). Both mean
    # composition is UNDEFINED — matches fuel.py's `if burn else None` for ALL such ZIPs.
    null_cols = ", ".join(
        f"case when burnable_frac is null or burnable_frac = 0 then null else {c} end as {c}"
        for c in COMPOSITION)
    select = ", ".join(others) + ", " + null_cols
    tmp = I / "fuel_context.__tmp.parquet"
    con.execute(f"copy (select {select} from '{src}') to '{tmp}' (format parquet)")
    shutil.move(tmp, src)


def main():
    con = duckdb.connect()

    # 1. fuel NULL-correctness (in interim, the source of truth)
    fix_fuel_nulls(con)
    src = f"'{I/'fuel_context.parquet'}'"
    nb = con.execute(f"select count(*) from {src} where shrub_frac is null").fetchone()[0]
    nr = con.execute(f"select count(*) from {src} where shrub_frac is null and total_px=0").fetchone()[0]
    z0 = con.execute(f"select count(*) from {src} where shrub_frac is null and burnable_frac=0").fetchone()[0]
    print(f"fuel NULL fix: {nb} ZIPs now have NULL composition ({nr} no-raster + {z0} nothing-burnable) "
          f"— true parquet null, matching fuel.py's `if burn else None`")

    # 2. copy the three into data/
    for stem in PROMOTE.values():
        shutil.copy(I / f"{stem}.parquet", DATA / f"{stem}.parquet")
        n = con.execute(f"select count(*) from '{DATA/f'{stem}.parquet'}'").fetchone()[0]
        print(f"promoted {stem}.parquet -> data/  ({n} rows)")

    # 3. manifest: register tables + drop "(interim)" markers (state untouched)
    mpath = DATA / "manifest.json"
    m = json.loads(mpath.read_text())
    for stem in PROMOTE.values():
        cols = con.execute(f"select * from '{DATA/f'{stem}.parquet'}' limit 0").df().columns.tolist()
        rows = con.execute(f"select count(*) from '{DATA/f'{stem}.parquet'}'").fetchone()[0]
        m["tables"][stem] = {"rows": rows, "columns": cols}
    for domkey, stem in PROMOTE.items():
        m["metric_domains"][domkey]["tables"] = [stem]   # drop the "(interim)" suffix
    mpath.write_text(json.dumps(m, indent=2) + "\n")
    print("manifest.tables updated; domain markers de-interim'd; state stays 'additive'")

    # grain confirmation (what the developer asked to see)
    print("\nGRAIN CONFIRMATION:")
    for stem, expect in [("nri_zip", 1693), ("zip_priority_matrix", 1693), ("fuel_context", 1801)]:
        n = con.execute(f"select count(distinct zip) from '{DATA/f'{stem}.parquet'}'").fetchone()[0]
        print(f"  {stem}: {n} ZIPs (expected {expect}) {'OK' if n == expect else 'MISMATCH'}")
    fc = f"'{DATA/'fuel_context.parquet'}'"
    z = con.execute(f"select count(*) from {fc} where shrub_frac is null").fetchone()[0]
    zr = con.execute(f"select count(*) from {fc} where shrub_frac is null and total_px=0").fetchone()[0]
    zb = con.execute(f"select count(*) from {fc} where shrub_frac is null and burnable_frac=0").fetchone()[0]
    ok = (z == 34 and zr == 22 and zb == 12)
    print(f"  fuel NULL composition: {z} (= {zr} no-raster + {zb} nothing-burnable; "
          f"expected 34 = 22 + 12) {'OK' if ok else 'MISMATCH'}")


if __name__ == "__main__":
    main()
