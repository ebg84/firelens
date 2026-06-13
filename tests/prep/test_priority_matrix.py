"""Module 8b — hazard×exposure decision matrix (product feature).

FWI = fire hazard; NRI WFIR_EALT = human consequence. Two complementary, orthogonal
axes (NOT a validated-against relationship). The matrix earns its place by being
actionable per-quadrant; the near-zero correlation is a footnote, never the evidence.
Output is a categorical quadrant, never a blended risk score.
"""
import json

import pandas as pd

from prep import nri, paths

PM = paths.INTERIM / "zip_priority_matrix.parquet"
DIAG = paths.INTERIM / "nri_diagnostics.json"
QUADS = {"priority", "monitor", "harden", "low_priority"}


# ---- classification math (oracle, runs now) ----------------------------------

def test_quadrant_logic():
    assert nri.classify_quadrant(True, True) == "priority"
    assert nri.classify_quadrant(True, False) == "monitor"      # high hazard, low exposure
    assert nri.classify_quadrant(False, True) == "harden"       # low hazard, high exposure
    assert nri.classify_quadrant(False, False) == "low_priority"


def test_matrix_splits_at_median():
    df = pd.DataFrame({"zip": ["a", "b", "c", "d"],
                       "fwi_level": [10, 30, 10, 30], "wfir_ealt": [100, 100, 900, 900]})
    out, th = nri.build_priority_matrix(df)
    assert th["hazard_median"] == 20 and th["exposure_median"] == 500
    q = dict(zip(out["zip"], out["quadrant"]))
    assert q == {"a": "low_priority", "b": "monitor", "c": "harden", "d": "priority"}, q


# ---- gate (red until prep/09_priority_matrix.py runs) ------------------------

def _require():
    assert PM.exists() and DIAG.exists(), "run prep/09_priority_matrix.py first"


def test_every_zip_classified_into_a_quadrant():
    _require()
    import duckdb
    bad = duckdb.connect().execute(
        f"select count(*) from '{PM}' where quadrant is null or quadrant not in "
        f"('priority','monitor','harden','low_priority')").fetchone()[0]
    assert bad == 0


def test_quadrant_counts_sum_to_total():
    _require()
    import duckdb
    c = json.load(open(DIAG))["priority_matrix"]["counts"]
    total = duckdb.connect().execute(f"select count(*) from '{PM}'").fetchone()[0]
    assert sum(c.values()) == total and set(c) <= QUADS, c


def test_categorical_not_a_risk_score():
    """The guardrail: a quadrant label, not a blended number. The two axes stay
    separate columns; nothing multiplies them into one served risk value."""
    _require()
    import duckdb
    cols = duckdb.connect().execute(f"select * from '{PM}' limit 0").df().columns.tolist()
    assert "quadrant" in cols and "fwi_level" in cols and "wfir_ealt" in cols
    assert not any(c.lower() in ("risk", "score", "risk_score", "composite") for c in cols)


def test_death_valley_exhibit_is_monitor():
    """92328: CA's most extreme fire weather, near-zero exposure -> monitor
    (dangerous weather, nobody there). The exhibit the matrix must place correctly."""
    _require()
    import duckdb
    q = duckdb.connect().execute(f"select quadrant from '{PM}' where zip='92328'").fetchone()
    assert q is not None and q[0] == "monitor", q
