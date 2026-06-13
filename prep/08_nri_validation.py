"""prep/08_nri_validation.py — FEMA NRI wildfire VALIDATION layer (Module 8a).

Joins tract-level NRI wildfire fields to our CA ZCTAs via the HUD TRACT_ZIP crosswalk
(residential-weighted), then correlates per-ZIP NRI vs FireLens recent-era mean FWI.
NRI sits BESIDE FireLens as an external federal benchmark — never a served risk metric.

Reports: WFIR_AFREQ (annualized frequency — the rigorous hazard-to-hazard check) and
WFIR_RISKS (composite risk — the "we track the federal framework" headline), each as
Spearman (primary) + Pearson (secondary) vs recent-era mean FWI per ZIP.

Run:  python prep/08_nri_validation.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb
import pandas as pd

from prep import nri, paths


def main():
    raw = paths.DATA_ROOT / "raw"
    # NRI CA tracts (usecols -> fast over the 634 MB national file)
    n = pd.read_csv(raw / "nri" / "NRI_Table_CensusTracts.csv",
                    usecols=["TRACTFIPS", "STCOFIPS", "WFIR_RISKS", "WFIR_AFREQ", "WFIR_EALT"],
                    dtype={"TRACTFIPS": str, "STCOFIPS": str}, low_memory=False)
    n = n[n["STCOFIPS"].str.startswith("06")].rename(columns={
        "TRACTFIPS": "tract", "WFIR_RISKS": "wfir_risks",
        "WFIR_AFREQ": "wfir_afreq", "WFIR_EALT": "wfir_ealt"})
    for c in ["wfir_risks", "wfir_afreq", "wfir_ealt"]:
        n[c] = pd.to_numeric(n[c], errors="coerce")

    # HUD TRACT_ZIP crosswalk, CA tracts only
    x = pd.read_excel(raw / "crosswalks" / "TRACT_ZIP_122025.xlsx",
                      usecols=["TRACT", "ZIP", "RES_RATIO"], dtype={"TRACT": str, "ZIP": str})
    x = x[x["TRACT"].str.startswith("06")].rename(columns={
        "TRACT": "tract", "ZIP": "zip", "RES_RATIO": "res_ratio"})
    x["res_ratio"] = pd.to_numeric(x["res_ratio"], errors="coerce").fillna(0.0)

    served = set(duckdb.connect().execute(
        f"select zip from '{paths.INTERIM/'zip_meta.parquet'}'").df()["zip"])

    integ = nri.crosswalk_integrity(x)
    agg = nri.aggregate_to_zip(n, x, served)
    agg.drop(columns=["wsum"]).to_parquet(paths.INTERIM / "nri_zip.parquet", index=False)

    matched = set(agg["zip"])
    unmatched = served - matched
    # root-cause breakdown of every gap (x is already CA-tract rows):
    um_rows = x[x["zip"].isin(unmatched)]
    resmax = um_rows.groupby("zip")["res_ratio"].max()
    cov = {"served_total": len(served),
           "served_zips_matched_frac": len(matched & served) / len(served),
           "unmatched_served_frac": len(unmatched) / len(served),
           "unmatched_total": len(unmatched),
           "unmatched_non_residential": int((resmax <= 0).sum()),     # res_ratio=0 everywhere
           "unmatched_f8_absent": int(len(unmatched) - resmax.index.nunique()),  # not in HUD at all
           "unmatched_recoverable_bug": int((resmax > 0).sum()),       # MUST be 0 (else a join bug)
           "nri_ca_tracts": int(len(n)),
           "nri_tracts_in_crosswalk_frac": float(n["tract"].isin(set(x["tract"])).mean())}

    # correlation vs FireLens recent-era mean FWI (zip_trends.recent, metric='fwi')
    fl = duckdb.connect().execute(
        f"select zip, recent fwi_recent from '{paths.INTERIM/'zip_trends.parquet'}' "
        f"where metric='fwi'").df()
    mc = agg.merge(fl, on="zip", how="inner").dropna(subset=["fwi_recent", "wfir_afreq", "wfir_risks"])
    corr = {"n_zips": int(len(mc))}
    for field in ["wfir_afreq", "wfir_risks"]:
        corr[field] = {
            "spearman": round(mc[[field, "fwi_recent"]].corr("spearman").iloc[0, 1], 4),
            "pearson": round(mc[[field, "fwi_recent"]].corr("pearson").iloc[0, 1], 4)}

    diag = {"crosswalk": integ, "coverage": cov, "correlation": corr}
    (paths.INTERIM / "nri_diagnostics.json").write_text(json.dumps(diag, indent=2))

    print("=" * 64)
    print(f"NRI -> ZIP: {len(agg)} ZCTAs  (served {cov['served_total']}, "
          f"matched {cov['served_zips_matched_frac']:.3%})")
    print(f"crosswalk integrity: max dev from 1.0 = {integ['max_dev_from_1']:.4f}; "
          f"zero-residential tracts = {integ['zero_residential_tracts']}")
    print(f"NRI CA tracts in crosswalk: {cov['nri_tracts_in_crosswalk_frac']:.3%}")
    print(f"\nVALIDATION — NRI wildfire vs FireLens recent-era mean FWI  (n={corr['n_zips']} ZIPs):")
    print(f"  WFIR_AFREQ (hazard, rigor) : Spearman {corr['wfir_afreq']['spearman']:+.3f}  "
          f"Pearson {corr['wfir_afreq']['pearson']:+.3f}")
    print(f"  WFIR_RISKS (composite, hdln): Spearman {corr['wfir_risks']['spearman']:+.3f}  "
          f"Pearson {corr['wfir_risks']['pearson']:+.3f}")
    print("=" * 64)


if __name__ == "__main__":
    main()
