"""Real-scan coverage for the advisory dimension cheap enough to run per-test.

``audit_dead_code`` wraps a fast real scan and is exercised here against the
live tree. ``audit_security``
wraps a full-tree semgrep scan that alone takes minutes -- too slow for the
routine `dev/audit/tests` lane's per-test ceiling -- so its real-subprocess
path is covered by ``test_security_scan.py`` (scoped to a small subtree) plus
the fast unit coverage in ``test_advisory_report.py`` for the mapping logic;
``build_advisory_report``'s four-dimension composition is covered separately;
its full semgrep execution was verified manually (persisted summary.json/summary.md/
security-findings.json, all inspected) rather than carried as an automated
test that would routinely time out this lane.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..advisory import audit_dead_code
from ..report import Status, audit_layering

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


def test_audit_layering_reports_the_authoritative_gate_failure_as_red() -> None:
    """An unavailable import-quality gate is red, never an advisory amber."""
    missing_root = Path(tempfile.gettempdir()) / "cadrumo-layering-no-such-root"
    assert not missing_root.exists(), missing_root

    report = audit_layering(missing_root)

    assert report.name == "layering"
    assert report.status is Status.RED
    assert "exited" in report.headline or "could not run" in report.headline
    assert report.details
