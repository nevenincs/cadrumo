"""Monthly code-health report: composition, classification, and real invocation.

Exercises ``dev.audit.report`` -- the tool giving contributors monthly
shadowing/duplication/layering reports with red/amber severity. The
module composes the four EXISTING scanners already shipped under ``dev/``
(``dev.import_hygiene_scan`` Family-3 for shadowing, the ``jscpd`` wrapper for
duplication, ``lint-imports`` / ``.importlinter`` for layering,
``dev.audit.complexity`` for complexity) rather than re-implementing any of
them; these tests confirm the composition and the shared red/amber/green
severity model, not the underlying scanners (which carry their own tests).

Real behaviour throughout: the classification tests below feed the real
``DimensionReport``/``HealthReport`` dataclasses (no mocks needed -- they are
plain data), the parsing test feeds real captured jscpd console output, and
the end-to-end tests invoke the real dimension functions against the live
tree and assert the returned shape is internally consistent with the
underlying scanner it wraps.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dev.audit.report import (
    DimensionReport,
    HealthReport,
    Status,
    audit_complexity,
    audit_duplication,
    audit_layering,
    audit_shadowing,
    build_report,
)

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# HealthReport.overall: red/amber/green precedence
# ---------------------------------------------------------------------------


def test_overall_is_green_when_every_dimension_is_green() -> None:
    """All-clean dimensions yield an overall GREEN verdict."""
    report = HealthReport(
        dimensions=(
            DimensionReport(name="shadowing", status=Status.GREEN, headline="clean"),
            DimensionReport(name="duplication", status=Status.GREEN, headline="clean"),
            DimensionReport(name="layering", status=Status.GREEN, headline="clean"),
            DimensionReport(name="complexity", status=Status.GREEN, headline="clean"),
        ),
    )

    assert report.overall is Status.GREEN


def test_overall_is_amber_when_no_dimension_is_red_but_one_is_amber() -> None:
    """A single AMBER dimension with no RED dimension yields overall AMBER."""
    report = HealthReport(
        dimensions=(
            DimensionReport(name="shadowing", status=Status.GREEN, headline="clean"),
            DimensionReport(name="duplication", status=Status.AMBER, headline="3 clones"),
            DimensionReport(name="layering", status=Status.GREEN, headline="clean"),
            DimensionReport(name="complexity", status=Status.GREEN, headline="clean"),
        ),
    )

    assert report.overall is Status.AMBER


def test_overall_is_red_when_any_dimension_is_red_even_with_amber_present() -> None:
    """RED outranks AMBER: a single RED dimension makes the overall verdict RED."""
    report = HealthReport(
        dimensions=(
            DimensionReport(name="shadowing", status=Status.RED, headline="1 new duplicate"),
            DimensionReport(name="duplication", status=Status.AMBER, headline="3 clones"),
            DimensionReport(name="layering", status=Status.GREEN, headline="clean"),
            DimensionReport(name="complexity", status=Status.GREEN, headline="clean"),
        ),
    )

    assert report.overall is Status.RED


def test_to_json_round_trips_every_dimension_field() -> None:
    """``to_json`` carries every dimension's name, status, headline, and details."""
    report = HealthReport(
        dimensions=(
            DimensionReport(
                name="shadowing",
                status=Status.RED,
                headline="1 undocumented multi-facade duplicate symbol(s)",
                details=["Foo (facades=['aeat.a', 'aeat.b'])"],
            ),
        ),
    )

    payload = report.to_json()

    assert payload["overall"] == "red"
    assert payload["dimensions"] == [
        {
            "name": "shadowing",
            "status": "red",
            "headline": "1 undocumented multi-facade duplicate symbol(s)",
            "details": ["Foo (facades=['aeat.a', 'aeat.b'])"],
        }
    ]


# jscpd invocation, parsing, and availability classification are owned by
# ``dev.audit.duplication`` and covered by ``dev/audit/tests/test_duplication.py``
# against the real subprocess. The reduction tests that lived here were deleted
# with the second jscpd parser they exercised: one of them asserted that output
# carrying no summary at all reduces to "zero clones", which is precisely the
# false-green this report shipped for months. This module now tests only what it
# owns -- the composition and the severity model.


# ---------------------------------------------------------------------------
# Real end-to-end invocation: each dimension against the live tree
# ---------------------------------------------------------------------------


def test_audit_shadowing_returns_a_valid_dimension_report() -> None:
    """The shadowing dimension runs the real Family-3 scanner and classifies it."""
    result = audit_shadowing()

    assert result.name == "shadowing"
    assert result.status in {Status.RED, Status.AMBER, Status.GREEN}
    assert result.headline


def test_audit_shadowing_red_findings_are_never_in_the_tolerated_baseline() -> None:
    """Every RED-classified shadowing detail names a symbol NOT in the pinned baseline.

    This is the load-bearing correctness property distinguishing RED (a new,
    undocumented multi-facade duplicate) from AMBER (a pinned, already-reviewed
    one): if the classifier ever conflated the two, a genuinely new duplicate
    could hide inside the "grandfathered debt" bucket.
    """
    import json

    baseline_path = PROJECT_ROOT / "dev" / "import_hygiene_baseline.json"
    tolerated = {
        entry["symbol"]
        for entry in json.loads(baseline_path.read_text(encoding="utf-8"))["family3_pinned_duplicate_symbols"][
            "tolerated_multi_sourced_symbols"
        ]
    }

    result = audit_shadowing()

    if result.status is Status.RED:
        for detail in result.details:
            symbol = detail.split(" (facades=", 1)[0]
            assert symbol not in tolerated, f"RED-classified symbol {symbol!r} is in the tolerated baseline"


def test_audit_complexity_returns_a_valid_dimension_report() -> None:
    """The complexity dimension runs the real Radon/Complexipy scan and classifies it."""
    result = audit_complexity()

    assert result.name == "complexity"
    assert result.status in {Status.RED, Status.AMBER, Status.GREEN}
    assert result.headline


def test_audit_layering_returns_a_valid_dimension_report() -> None:
    """The layering dimension runs the real ``lint-imports`` contracts and classifies it.

    RED iff at least one contract reports BROKEN in the captured output;
    GREEN otherwise. There is no AMBER classification for this dimension
    (a layering contract is a hard boundary, never ratcheted debt) unless the
    ``lint-imports`` executable itself could not be found or run, which is a
    distinct AMBER "signal unavailable" outcome.
    """
    result = audit_layering(PROJECT_ROOT)

    assert result.name == "layering"
    assert result.status in {Status.RED, Status.AMBER, Status.GREEN}
    if result.status is Status.RED:
        assert result.details


def test_audit_duplication_reports_the_live_trees_real_duplication_state() -> None:
    """The duplication dimension classifies the live tree honestly.

    Never RED by design (clone count is advisory debt, never a hard break). The
    earlier form of this test asserted only ``status in {AMBER, GREEN}``, which
    holds no matter what the dimension says -- it passed happily while the
    dimension reported GREEN "no clones found" on a tree carrying 65 real
    clones. The live tree does carry clones, so AMBER with a measured count is
    the only honest verdict here; GREEN would mean the runner scanned nothing.
    """
    result = audit_duplication(PROJECT_ROOT)

    assert result.name == "duplication"
    assert result.status is Status.AMBER
    assert "clone cluster(s)" in result.headline


def test_build_report_composes_all_four_dimensions_in_order() -> None:
    """``build_report`` returns exactly the four named dimensions, in a fixed order."""
    report = build_report(PROJECT_ROOT)

    assert [d.name for d in report.dimensions] == ["shadowing", "duplication", "layering", "complexity"]
    assert report.overall in {Status.RED, Status.AMBER, Status.GREEN}


def test_project_root_points_at_the_real_repository_root() -> None:
    """Sanity: the fixture path used by the end-to-end tests is the real repo root."""
    assert (PROJECT_ROOT / ".importlinter").is_file()
    assert (Path(PROJECT_ROOT) / "dev" / "audit" / "report.py").is_file()
