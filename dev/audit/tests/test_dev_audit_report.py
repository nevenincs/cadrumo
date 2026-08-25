"""Monthly code-health report: composition, classification, and real invocation.

Exercises ``dev.audit.report`` -- the tool giving contributors monthly
shadowing/duplication/layering reports with red/amber severity. The
module composes the four EXISTING scanners already shipped under ``dev/``
(``dev.quality.import_hygiene_scan`` Family-3 for shadowing, the ``jscpd`` wrapper for
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

import shutil
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..report import (
    DimensionReport,
    HealthReport,
    Status,
    _declared_contract_count,
    audit_layering,
    build_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def live_health_report() -> HealthReport:
    """Run the composed audit over the real repository ONCE for this module.

    ``build_report`` calls ``audit_duplication(repo_root)`` and
    ``audit_complexity()`` -- the exact calls the per-dimension tests below made
    for themselves -- so every one of them re-ran a scan the composed report had
    already performed. Three tests measured 120.5s, 61.4s and 38.1s, and the
    second and third were re-deriving what the first already held.

    The dimensions read out of this report are the SAME objects those functions
    return; nothing here weakens what the tests assert. What is given up is
    proving the two functions are callable standalone, which ``build_report``
    exercises anyway by calling them.
    """
    return build_report(REPO_ROOT)


def _dimension(report: HealthReport, name: str) -> DimensionReport:
    """Return the named dimension, refusing rather than skipping if absent."""
    for dimension in report.dimensions:
        if dimension.name == name:
            return dimension
    raise AssertionError(f"composed report carries no {name!r} dimension: {[d.name for d in report.dimensions]}")


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


def test_audit_shadowing_returns_a_valid_dimension_report(live_health_report: HealthReport) -> None:
    """The shadowing dimension runs the real Family-3 scanner and classifies it.

    Read from the composed report for the same reason the complexity and
    duplication dimensions are: ``build_report`` obtains this dimension by
    calling ``audit_shadowing()`` and stores the returned object unchanged, so
    this reads the identical object the standalone call produced. The scanner
    measured ~15s per run and this module invoked it three times.
    """
    result = _dimension(live_health_report, "shadowing")

    assert result.name == "shadowing"
    assert result.status in {Status.RED, Status.AMBER, Status.GREEN}
    assert result.headline


def test_audit_shadowing_red_findings_are_never_in_the_tolerated_baseline(
    live_health_report: HealthReport,
) -> None:
    """Every RED-classified shadowing detail names a symbol NOT in the pinned baseline.

    This is the load-bearing correctness property distinguishing RED (a new,
    undocumented multi-facade duplicate) from AMBER (a pinned, already-reviewed
    one): if the classifier ever conflated the two, a genuinely new duplicate
    could hide inside the "grandfathered debt" bucket.
    """
    import json

    baseline_path = REPO_ROOT / "dev" / "quality" / "import_hygiene_baseline.json"
    tolerated = {
        entry["symbol"]
        for entry in json.loads(baseline_path.read_text(encoding="utf-8"))["family3_pinned_duplicate_symbols"][
            "tolerated_multi_sourced_symbols"
        ]
    }

    result = _dimension(live_health_report, "shadowing")

    if result.status is Status.RED:
        for detail in result.details:
            symbol = detail.split(" (facades=", 1)[0]
            assert symbol not in tolerated, f"RED-classified symbol {symbol!r} is in the tolerated baseline"


def test_audit_complexity_returns_a_valid_dimension_report(live_health_report: HealthReport) -> None:
    """The complexity dimension runs the real Radon/Complexipy scan and classifies it.

    Read from the composed report, which obtained it by calling
    ``audit_complexity()`` -- the identical call this test used to make for
    itself, on the same live tree.
    """
    result = _dimension(live_health_report, "complexity")

    assert result.name == "complexity"
    assert result.status in {Status.RED, Status.AMBER, Status.GREEN}
    assert result.headline


def test_audit_layering_evaluates_every_declared_contract() -> None:
    """The layering dimension must report over every contract, not merely exit.

    The prior form of this test asserted ``status in {RED, AMBER, GREEN}``,
    which is the whole enum and therefore holds no matter what the dimension
    says -- the same tautology the duplication test below records against its
    own earlier form. It would have passed throughout the period the contracts
    were not being evaluated at all.

    The load-bearing assertion is the floor: the run must have EVALUATED as
    many contracts as ``.importlinter`` DECLARES. A run reporting nothing is
    not a clean run.
    """
    declared = _declared_contract_count(REPO_ROOT)
    assert declared > 0, ".importlinter declares no contracts; the layering signal has no subject"

    # Availability is asserted, not tolerated. An early return on the
    # unavailable-tool AMBER would let this whole test pass while checking
    # nothing -- the same shape it exists to catch. lint-imports is a declared
    # dev dependency, so its absence is a broken environment worth failing on.
    assert shutil.which("lint-imports") is not None, (
        "lint-imports is not on PATH, so the layering floor below would pass without "
        "evaluating anything; install the dev dependencies rather than skipping this"
    )

    result = audit_layering(REPO_ROOT)

    assert result.name == "layering"
    assert result.status is not Status.AMBER, (
        f"the executable resolved, so AMBER 'signal unavailable' cannot apply: {result.headline!r}"
    )
    assert f"of {declared} import-linter contract(s)" in result.headline, (
        f"headline must state how many of the {declared} declared contracts were evaluated, "
        f"so an aborted run cannot read as a clean one: {result.headline!r}"
    )
    if result.status is Status.RED:
        assert result.details


def test_audit_layering_reports_an_aborted_run_distinctly_from_a_breach(tmp_path: Path) -> None:
    """A stale ignore aborts the whole run; that must not read as a violation.

    Real behaviour, no mocking: this copies the live ``.importlinter``, injects
    an ``ignore_imports`` entry naming a module that does not exist, and runs
    the real ``lint-imports`` against it. import-linter refuses the unmatched
    entry and exits non-zero WITHOUT evaluating a single contract, printing no
    KEPT or BROKEN lines at all.

    That is the exact state which once left five contracts unchecked while the
    output read as short and unremarkable. Classified by exit code alone it
    reads as "contracts broken"; classified by the absence of BROKEN lines it
    reads as GREEN. Both are wrong in the same direction, so the dimension has
    to compare evaluated against declared and say which failure it is.
    """
    config = (REPO_ROOT / ".importlinter").read_text(encoding="utf-8", errors="replace")
    marker = "ignore_imports ="
    assert marker in config, "expected at least one ignore_imports block to inject into"
    cut = config.index(marker) + len(marker)
    stale = "\n    cadrumo.this.module.does.not.exist -> cadrumo.core"
    (tmp_path / ".importlinter").write_text(config[:cut] + stale + config[cut:], encoding="utf-8")

    result = audit_layering(tmp_path)

    assert result.status is not Status.AMBER, (
        f"lint-imports resolved for the sibling test, so an unavailable-tool AMBER here would "
        f"mean the abort path went unexercised: {result.headline!r}"
    )

    declared = _declared_contract_count(tmp_path)
    assert result.status is Status.RED
    assert f"evaluated 0 of {declared}" in result.headline, (
        f"an aborted run must say how little it evaluated, not imply a breach: {result.headline!r}"
    )
    assert "aborted" in result.headline
    assert "broken" not in result.headline, (
        f"an aborted run reported zero contracts, so it must not claim a breach: {result.headline!r}"
    )
    assert result.details and "stale" in result.details[0].lower(), (
        "the detail must name the rotted configuration so a reader knows to fix the ignore list "
        "rather than hunt for a layering violation that was never reported"
    )


def test_audit_duplication_reports_the_live_trees_real_duplication_state(
    live_health_report: HealthReport,
) -> None:
    """The duplication dimension classifies the live tree honestly.

    Never RED by design (clone count is advisory debt, never a hard break). The
    earlier form of this test asserted only ``status in {AMBER, GREEN}``, which
    holds no matter what the dimension says -- it passed happily while the
    dimension reported GREEN "no clones found" on a tree carrying 65 real
    clones. The live tree does carry clones, so AMBER with a measured count is
    the only honest verdict here; GREEN would mean the runner scanned nothing.
    """
    result = _dimension(live_health_report, "duplication")

    assert result.name == "duplication"
    assert result.status is Status.AMBER
    assert "clone cluster(s)" in result.headline


def test_build_report_composes_all_four_dimensions_in_order(live_health_report: HealthReport) -> None:
    """``build_report`` returns exactly the four named dimensions, in a fixed order."""
    report = live_health_report

    assert [d.name for d in report.dimensions] == ["shadowing", "duplication", "layering", "complexity"]
    assert report.overall in {Status.RED, Status.AMBER, Status.GREEN}


def test_project_root_points_at_the_real_repository_root() -> None:
    """Sanity: the fixture path used by the end-to-end tests is the real repo root."""
    assert (REPO_ROOT / ".importlinter").is_file()
    assert (Path(REPO_ROOT) / "dev" / "audit" / "report.py").is_file()
