"""prep/meta_validate.py — MUTATION TEST of the validation suite itself.

Validates the VALIDATION PROCESS: for every critical gate, deliberately inject the
failure it is supposed to catch and confirm the ACTUAL committed check goes RED. A
check that stays GREEN on corrupted data is theater and is reported as such.

SAFETY: operates entirely on a symlink mirror in a temp dir. The served data/ and the
interim/ layer are NEVER mutated — corruption writes a real parquet OVER a symlink in
the mirror only. Reads clean source, writes corrupt copy, runs the real check.

Run: python prep/meta_validate.py   (read-only w.r.t. the served layer)
"""
import importlib
import json
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb
import pandas as pd

from prep import paths

CLEAN_DATA = paths.REPO_ROOT / "data"
CLEAN_INTERIM = paths.INTERIM


# ---- mirror plumbing ---------------------------------------------------------

def build_mirror():
    """Symlink every clean file into tmp/{data,interim}. Symlinks cost nothing, so the
    637 MB spine is mirrored for free; corruption replaces a link with a real file."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="firelens_mut_"))
    for sub, clean in [("data", CLEAN_DATA), ("interim", CLEAN_INTERIM)]:
        (root / sub).mkdir(parents=True)
        for f in clean.iterdir():
            if f.is_file():
                (root / sub / f.name).symlink_to(f)
    return root


def corrupt(root, sub, name, transform):
    """Read the CLEAN parquet, apply transform(df)->df, write a real file over the
    mirror's symlink. Returns the path written."""
    clean = (CLEAN_DATA if sub == "data" else CLEAN_INTERIM) / name
    df = duckdb.connect().execute(f"select * from '{clean}'").df()
    df = transform(df)
    target = root / sub / name
    if target.is_symlink():
        target.unlink()
    df.to_parquet(target)
    return target


def restore(root, sub, name):
    """Re-link a corrupted file back to clean (so each mutation starts from green)."""
    clean = (CLEAN_DATA if sub == "data" else CLEAN_INTERIM) / name
    target = root / sub / name
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(clean)


# ---- run a committed check, capture RED/GREEN --------------------------------

def run_validate_check(root, fn_name):
    """Point prep.validate at the mirror, call the named check, return passed bool."""
    from prep import validate
    validate.D = root / "data"
    validate.I = root / "interim"
    r = getattr(validate, fn_name)()
    return r["passed"], r["detail"]


def run_pytest_fn(module_name, const_overrides, fn_name):
    """Import a committed test module, override its path constants to the mirror, call
    the test fn. Returns ('RED', None) if it raises AssertionError (teeth), ('GREEN', None)
    if it passes (theater for this mutation), or ('ERROR', msg)."""
    mod = importlib.import_module(module_name)
    saved = {k: getattr(mod, k) for k in const_overrides}
    for k, v in const_overrides.items():
        setattr(mod, k, v)
    try:
        getattr(mod, fn_name)()
        return "GREEN", None
    except AssertionError:
        return "RED", None
    except Exception as e:
        return "ERROR", f"{type(e).__name__}: {e}"
    finally:
        for k, v in saved.items():
            setattr(mod, k, v)


RESULTS = []


def record(gate, mutation, committed_check, observed_red, note=""):
    teeth = "TEETH" if observed_red else "THEATER"
    RESULTS.append({"gate": gate, "mutation": mutation, "check": committed_check,
                    "went_red": observed_red, "verdict": teeth, "note": note})
    print(f"  [{teeth:7}] {gate}: {mutation}\n            check={committed_check} -> {'RED' if observed_red else 'GREEN'}"
          + (f"  ({note})" if note else ""))


# ---- the mutations -----------------------------------------------------------

def main():
    root = build_mirror()
    print(f"mirror: {root}\n")

    # M1 — ORPHAN ZIP: drop a ZIP from zip_cell_map -> a served ZIP has no weather cell.
    z = "95404"
    corrupt(root, "data", "zip_cell_map.parquet", lambda d: d[d["zip"] != z])
    passed, _ = run_validate_check(root, "check_zip_cell_map")
    record("orphan ZIP", f"drop {z} from zip_cell_map", "validate.check_zip_cell_map", not passed)
    restore(root, "data", "zip_cell_map.parquet")

    # M2 — KEY MISFORMAT (GEOID): truncate a ZIP to 4 digits in zip_trends.
    corrupt(root, "data", "zip_trends.parquet",
            lambda d: d.assign(zip=d["zip"].mask(d["zip"] == "95404", "9540")))
    passed, _ = run_validate_check(root, "check_cross_metric_key_alignment")
    record("key alignment", "4-digit ZIP in zip_trends", "validate.check_cross_metric_key_alignment", not passed)
    # same mutation vs the canonical-set gate
    red, _ = run_pytest_fn("tests.prep.test_domains",
                           {"D": root / "data", "I": root / "interim", "MANIFEST": root / "data" / "manifest.json"},
                           "test_served_zip_metrics_match_canonical_set")
    record("key alignment", "4-digit ZIP in zip_trends", "test_domains.test_served_zip_metrics_match_canonical_set", red == "RED")
    restore(root, "data", "zip_trends.parquet")

    # M3 — OUT-OF-RANGE DATE: stamp a 2099 ignition into fire_events.
    def _bad_date(d):
        d = d.copy()
        d.loc[d.index[0], "ign_date"] = pd.Timestamp("2099-07-01")
        return d
    corrupt(root, "data", "fire_events.parquet", _bad_date)
    passed, det = run_validate_check(root, "check_temporal_ranges")
    record("range bounds (date)", "2099 ign_date in fire_events", "validate.check_temporal_ranges", not passed)
    red, _ = run_pytest_fn("tests.prep.test_domains",
                           {"D": root / "data", "I": root / "interim", "MANIFEST": root / "data" / "manifest.json"},
                           "test_fire_events_point_to_cell_in_range")
    record("range bounds (date)", "2099 ign_date in fire_events", "test_domains.test_fire_events_point_to_cell_in_range", red == "RED")
    restore(root, "data", "fire_events.parquet")

    # M4 — NULL -> FABRICATED VALUE: replace the 4 null fwi_pctile with a fabricated 0.5,
    # and fabricate structures_destroyed (100% null) = 5636 on Tubbs. Run EVERY committed
    # fire_events gate; if all stay GREEN this class is unguarded.
    def _fabricate(d):
        d = d.copy()
        d["fwi_pctile"] = d["fwi_pctile"].fillna(0.5)
        d.loc[d["name"].str.upper() == "TUBBS", "structures_destroyed"] = 5636
        return d
    corrupt(root, "data", "fire_events.parquet", _fabricate)
    corrupt(root, "interim", "fire_events.parquet", _fabricate)
    fe_greens = []
    p1, _ = run_validate_check(root, "check_temporal_ranges"); fe_greens.append(p1)
    for mod, fn in [("tests.prep.test_pairing", "test_fwi_pctile_in_unit_range"),
                    ("tests.prep.test_pairing", "test_tubbs_anchor_ge_90th_percentile"),
                    ("tests.prep.test_pairing", "test_no_duplicate_fire_id")]:
        red, _ = run_pytest_fn(mod, {"FE": root / "interim" / "fire_events.parquet"}, fn)
        fe_greens.append(red == "GREEN")
    all_green = all(fe_greens)
    record("NULL-not-fabricated", "fill null fwi_pctile=0.5 + fabricate structures=5636",
           "ALL fire_events gates", not all_green,
           note="NO committed check guards null->value fabrication" if all_green else "some gate caught it")
    restore(root, "data", "fire_events.parquet")
    restore(root, "interim", "fire_events.parquet")

    # M5 — DENOM-CORRECT AGGREGATION: monkeypatch nri.aggregate_to_zip to a BARE SUM
    # (no Σ-weight denominator) and confirm the oracle test fails.
    from prep import nri
    real_agg = nri.aggregate_to_zip
    def bare_sum_agg(nri_tract, xwalk, served_zips):
        out = real_agg(nri_tract, xwalk, served_zips).copy()
        for c in nri.INTENSIVE:                 # undo the /wsum -> bare allocation
            out[c] = out[c] * out["wsum"]
        return out
    nri.aggregate_to_zip = bare_sum_agg
    red, _ = run_pytest_fn("tests.prep.test_nri", {}, "test_intensive_uses_denominator_extensive_does_not")
    record("denom-correct agg", "bare-sum instead of weighted-average", "test_nri.test_intensive_uses_denominator", red == "RED")
    nri.aggregate_to_zip = real_agg

    # M6 — FRACTION-SUM-TO-1: skew one ZIP's burnable composition to sum 1.3.
    def _skew_frac(d):
        d = d.copy()
        i = d.index[(d["burnable_frac"] > 0)][0]
        d.loc[i, "shrub_frac"] = d.loc[i, "shrub_frac"] + 0.3
        return d
    corrupt(root, "interim", "fuel_context.parquet", _skew_frac)
    red, _ = run_pytest_fn("tests.prep.test_fuel", {"FUEL": root / "interim" / "fuel_context.parquet"},
                           "test_burnable_composition_sums_to_one")
    record("fraction-sum-to-1", "shrub_frac +0.3 (sum->1.3)", "test_fuel.test_burnable_composition_sums_to_one", red == "RED")
    restore(root, "interim", "fuel_context.parquet")

    # M7 — VALUE RANGE BOUNDS: wfir_risks=250 (>100), and season_len=9999 (>366).
    corrupt(root, "interim", "nri_zip.parquet",
            lambda d: d.assign(wfir_risks=d["wfir_risks"].mask(d.index == d.index[0], 250.0)))
    red, _ = run_pytest_fn("tests.prep.test_nri",
                           {"NRI_ZIP": root / "interim" / "nri_zip.parquet", "DIAG": root / "interim" / "nri_diagnostics.json"},
                           "test_wfir_ranges_sane")
    record("range bounds (value)", "wfir_risks=250 (>100)", "test_nri.test_wfir_ranges_sane", red == "RED")
    restore(root, "interim", "nri_zip.parquet")

    def _bad_season(d):
        d = d.copy()
        d.loc[d.index[0], "season_len"] = 9999
        return d
    corrupt(root, "interim", "annual_metrics.parquet", _bad_season)
    red, _ = run_pytest_fn("tests.prep.test_aggregates", {"ANNUAL": root / "interim" / "annual_metrics.parquet"},
                           "test_annual_sanity_and_non_degenerate")
    record("range bounds (value)", "season_len=9999 (>366)", "test_aggregates.test_annual_sanity", red == "RED")
    restore(root, "interim", "annual_metrics.parquet")

    # M8 — WEIGHTS-SUM-TO-1: break a ZIP's zip_cell_map weights to sum 0.5.
    def _halve_weights(d):
        d = d.copy()
        idx = d.index[d["zip"] == "90272"]
        d.loc[idx, "weight"] = d.loc[idx, "weight"] * 0.5
        return d
    corrupt(root, "data", "zip_cell_map.parquet", _halve_weights)
    passed, _ = run_validate_check(root, "check_zip_cell_map")
    record("weights sum to 1", "halve 90272 weights (sum->0.5)", "validate.check_zip_cell_map", not passed)
    restore(root, "data", "zip_cell_map.parquet")

    # M9 — NEGATIVE-CONTROL: a NO-OP 'corruption' (rewrite identical) must stay GREEN.
    # Proves RED in M1-M8 is the mutation, not the harness mechanics.
    corrupt(root, "data", "zip_cell_map.parquet", lambda d: d)
    passed, _ = run_validate_check(root, "check_zip_cell_map")
    record("negative control", "rewrite zip_cell_map unchanged", "validate.check_zip_cell_map", not passed,
           note="EXPECTED GREEN — if this is TEETH the harness is broken" if passed else "HARNESS BUG: green data went red")
    restore(root, "data", "zip_cell_map.parquet")

    # ---- summary ----
    theater = [r for r in RESULTS if not r["went_red"] and r["gate"] != "negative control"
               and r["gate"] != "NULL-not-fabricated"]
    gaps = [r for r in RESULTS if r["gate"] == "NULL-not-fabricated" and not r["went_red"]]
    print("\n" + "=" * 78)
    print(f"SUMMARY: {sum(1 for r in RESULTS if r['went_red'])} gates showed TEETH; "
          f"{len(theater)} unexpected THEATER; {len(gaps)} coverage GAP (null-fabrication).")
    if theater:
        print("THEATER (check stayed green on data it should reject):")
        for r in theater:
            print(f"  - {r['gate']} / {r['check']}")
    shutil.rmtree(root)
    return RESULTS


if __name__ == "__main__":
    main()
