"""prep/nri.py — FEMA NRI -> per-ZIP aggregation (importable; Module 8a).

Validation reference, not a served risk metric. Intensive fields (a score, a rate)
are residential-weighted AVERAGES with an explicit Σ(weight) denominator; the
extensive field (dollars) is a bare allocation. NRI is tract-level; the HUD TRACT_ZIP
crosswalk's RES_RATIO sums to ~1.0 per TRACT (allocates a tract across ZIPs), so a
per-ZIP average MUST normalize by Σ(RES_RATIO) within the ZIP.
"""
import pandas as pd

INTENSIVE = ["wfir_risks", "wfir_afreq"]   # score / rate -> weighted average
EXTENSIVE = ["wfir_ealt"]                  # dollars -> allocation (bare sum)


def aggregate_to_zip(nri_tract, xwalk, served_zips):
    """nri_tract: [tract, wfir_risks, wfir_afreq, wfir_ealt]. xwalk: [tract, zip,
    res_ratio]. served_zips: iterable of CA ZCTAs. Returns per-ZIP frame."""
    served = set(served_zips)
    m = xwalk.merge(nri_tract, on="tract", how="inner")
    m = m[m["zip"].isin(served) & (m["res_ratio"] > 0)].copy()
    for c in INTENSIVE + EXTENSIVE:
        m[c + "_wv"] = m[c] * m["res_ratio"]
    agg = m.groupby("zip").agg(
        wsum=("res_ratio", "sum"), n_tracts=("tract", "size"),
        **{c + "_wv": (c + "_wv", "sum") for c in INTENSIVE + EXTENSIVE}).reset_index()
    for c in INTENSIVE:
        agg[c] = agg[c + "_wv"] / agg["wsum"]   # weighted average (explicit denominator)
    for c in EXTENSIVE:
        agg[c] = agg[c + "_wv"]                 # extensive allocation
    return agg[["zip", "n_tracts", "wsum"] + INTENSIVE + EXTENSIVE]


QUADRANT = {(True, True): "priority", (True, False): "monitor",
            (False, True): "harden", (False, False): "low_priority"}


def classify_quadrant(hazard_high, exposure_high):
    """hazard × exposure -> intervention quadrant. The matrix earns its place by being
    actionable per-quadrant, NOT by any correlation statistic (the axes are orthogonal
    by construction — that is the reason to show both, kept as a footnote, not evidence)."""
    return QUADRANT[(bool(hazard_high), bool(exposure_high))]


def build_priority_matrix(df, hazard_col="fwi_level", exposure_col="wfir_ealt"):
    """Per-ZIP 2x2 classification, split at the statewide MEDIAN of each axis. NOT a
    blended risk score — the output is a categorical quadrant, the two axes stay visible."""
    d = df.dropna(subset=[hazard_col, exposure_col]).copy()
    hmed, emed = d[hazard_col].median(), d[exposure_col].median()
    d["hazard_high"] = d[hazard_col] > hmed
    d["exposure_high"] = d[exposure_col] > emed
    d["quadrant"] = [classify_quadrant(h, e)
                     for h, e in zip(d["hazard_high"], d["exposure_high"])]
    return d, {"hazard_median": float(hmed), "exposure_median": float(emed)}


def crosswalk_integrity(xwalk):
    """Σ res_ratio per tract; among residential tracts (sum>0) it must be ~1.0.
    Zero-residential tracts (industrial/water) legitimately sum to 0."""
    s = xwalk.groupby("tract")["res_ratio"].sum()
    resid = s[s > 1e-9]
    return {"tracts": int(len(s)),
            "zero_residential_tracts": int((s <= 1e-9).sum()),
            "max_dev_from_1": float((resid - 1.0).abs().max()),
            "mean_residential_sum": float(resid.mean())}
