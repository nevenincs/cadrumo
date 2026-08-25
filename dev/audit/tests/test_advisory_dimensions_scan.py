"""Real-scan coverage for the two advisory dimensions cheap enough to run per-test.

``audit_dead_code`` and ``audit_checkout_drift`` wrap fast real scans (a few
seconds each) and are exercised here against the live tree. ``audit_security``
wraps a full-tree semgrep scan that alone takes minutes -- too slow for the
routine `dev/audit/tests` lane's per-test ceiling -- so its real-subprocess
path is covered by ``test_security_scan.py`` (scoped to a small subtree) plus
the fast unit coverage in ``test_advisory_report.py`` for the mapping logic;
``build_advisory_report``'s full five-dimension composition was verified
manually end-to-end (47-line dashboard, persisted summary.json/summary.md/
security-findings.json, all inspected) rather than carried as an automated
test that would routinely time out this lane.
"""

from __future__ import annotations

import pytest

from ..._paths import REPO_ROOT
from ..advisory import audit_checkout_drift, audit_dead_code
from ..report import Status

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def test_audit_dead_code_returns_a_valid_dimension_against_the_live_tree() -> None:
    """A real vulture run classifies to a valid AdvisoryDimension, never a crash."""
    dimension = audit_dead_code(_REPO_ROOT)

    assert dimension.report.name == "dead_code"
    assert dimension.report.status in {Status.RED, Status.AMBER, Status.GREEN}
    assert dimension.report.headline
    # AMBER is the ceiling for this dimension by design -- see the function's
    # own docstring: dead code has never been a blocking gate, so a real run
    # must never surface RED here regardless of what vulture finds.
    assert dimension.report.status is not Status.RED


def test_audit_checkout_drift_returns_a_valid_dimension_against_the_live_tree() -> None:
    """A real byte-drift measurement classifies to a valid AdvisoryDimension."""
    dimension = audit_checkout_drift(_REPO_ROOT)

    assert dimension.report.name == "checkout_drift"
    assert dimension.report.status in {Status.RED, Status.AMBER, Status.GREEN}
    assert dimension.report.headline
    assert "scanned" in dimension.report.headline
