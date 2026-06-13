"""Re-runnable gate for the full spatial+temporal join-resolution sweep (prep/validate.py).

Each of the 7 checks is a parametrized gate: if a future join breaks a zone mapping,
drifts a metric off its universe, or leaks a temporal domain, the matching check goes RED.
"""
import pytest

from prep import validate


@pytest.mark.parametrize("check", validate.CHECKS, ids=[c.__name__ for c in validate.CHECKS])
def test_join_resolution(check):
    r = check()
    assert r["passed"], f"{r['check']} FAILED -> {r['detail']}"
