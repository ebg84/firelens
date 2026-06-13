"""prep/09_priority_matrix.py — hazard×exposure decision matrix (Module 8b).

Crosses FireLens FWI hazard (recent-era level, spine metric) with NRI WFIR_EALT
consequence (from 8a) into a per-ZIP intervention quadrant, split at statewide medians:
  priority      high hazard + high exposure   (danger zone — manage fuel AND harden)
  monitor       high hazard + low exposure    (Death Valley — dangerous weather, nobody there)
  harden        low hazard + high exposure    (dense built value, moderate weather)
  low_priority  low + low
Categorical output, NOT a blended risk score; the two axes stay visible. The near-zero
hazard/exposure correlation is the reason to show both — kept as a footnote, never the
evidence (the quadrants earn their place by being actionable).

Run:  python prep/09_priority_matrix.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb

from prep import nri, paths


def main():
    con = duckdb.connect()
    z = con.execute(f"select zip, wfir_ealt from '{paths.INTERIM/'nri_zip.parquet'}'").df()
    fl = con.execute(f"select zip, recent fwi_level from '{paths.INTERIM/'zip_trends.parquet'}' "
                     f"where metric='fwi'").df()
    df = z.merge(fl, on="zip")

    mat, th = nri.build_priority_matrix(df, hazard_col="fwi_level", exposure_col="wfir_ealt")
    out = mat[["zip", "fwi_level", "wfir_ealt", "quadrant"]]
    out.to_parquet(paths.INTERIM / "zip_priority_matrix.parquet", index=False)

    counts = out["quadrant"].value_counts().to_dict()
    exhibits = {z: (out.loc[out.zip == z, "quadrant"].iloc[0] if (out.zip == z).any() else None)
                for z in ["92328", "90272", "95404", "94588"]}
    # a genuine 'harden' exemplar from the data (low hazard, highest exposure)
    hardn = out[out.quadrant == "harden"].sort_values("wfir_ealt", ascending=False).head(1)
    harden_ex = hardn["zip"].iloc[0] if len(hardn) else None

    diag = json.load(open(paths.INTERIM / "nri_diagnostics.json"))
    diag["priority_matrix"] = {"thresholds": th, "counts": {k: int(v) for k, v in counts.items()},
                               "exhibits": exhibits, "harden_exemplar": harden_ex,
                               "axes": {"hazard": "fwi recent-era level", "exposure": "WFIR_EALT"}}
    (paths.INTERIM / "nri_diagnostics.json").write_text(json.dumps(diag, indent=2))

    print("=" * 60)
    print(f"PRIORITY MATRIX — split at FWI {th['hazard_median']:.1f} × "
          f"EALT ${th['exposure_median']:,.0f}  (n={len(out)})")
    for q in ["priority", "monitor", "harden", "low_priority"]:
        print(f"  {q:13s}: {counts.get(q, 0):4d}")
    print("\nexhibits:")
    for z, name in [("92328", "Death Valley"), ("90272", "Pac Palisades"),
                    ("95404", "Santa Rosa"), ("94588", "Pleasanton")]:
        print(f"  {z} {name:14s} -> {exhibits.get(z)}")
    print(f"  harden exemplar (low-hazard, highest exposure): {harden_ex}")
    print("=" * 60)


if __name__ == "__main__":
    main()
