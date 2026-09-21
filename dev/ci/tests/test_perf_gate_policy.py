"""The ``perf`` cohort's placement and ownership across the CI contract paths.

``dev/packaging/tests/test_perf_gate_policy.py`` asks these questions of
``dev/packaging/tests`` and only that directory. This file asks them of the
three directories the CI contract lane runs, because the blind spot between
them was not theoretical: all three CPU budgets in
``test_ledger_scale_benchmark.py`` carried ``serial`` and no ``perf``, so the
merge gate's serial leg selected them and asserted a calibrated CPU ceiling on
a runner ``.github/ci-control-plane.md`` documents as shared with other
tenants. Both ownership gates stayed green throughout, because neither looks
here.

The reading that would have caught it is the first one below, and it is the
reason this file exists rather than a second copy of the placement checks: a
test asserting a measured duration against a module-level constant budget is
asserting a threshold somebody calibrated on some machine, and ``perf`` is the
marker that says where such a threshold may be asserted.

The distinction is drawn at a CONSTANT deliberately, and two live tests sit on
the other side of it by design:

* ``test_overview_verbs.py`` compares two measurements taken back to back in
  one process. Contention scales both sides, so it binds a ratio rather than a
  calibration, and it is not a perf gate.
* ``test_self_hosted_fleet.py`` bounds a catastrophic-backtracking guard with
  an inline literal chosen for asymptotic headroom -- the failing shape exceeds
  it by orders of magnitude. Moving it to ``perf`` would take a real
  correctness check out of the merge gate and buy nothing.

Neither names a constant budget, so neither is reported, and that is the rule
doing its job rather than an exemption list. An exemption list is what this
file refuses to grow: every entry in one is a defect somebody decided not to
fix, and the next reader cannot tell those from the ones that were genuinely
fine.

The overlap with the packaging file is DELIBERATE and was decided rather than
overlooked. Two files asking the same questions of different trees catch
distinct failures, which is the justification the quality gates require for
overlapping coverage; the cost is maintenance, not detection. Sharing the
machinery would mean a new module both can import, and that placement decision
is not worth taking while this rule is still young -- it has already been
corrected once, to require that the module actually read a clock. Revisit when
a third directory needs the same policy, or when the two files' rules diverge
in a way nobody intended.
"""

from __future__ import annotations

import ast
import functools
import re
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT

from ..lane_reachability import Lane, declared_lanes, expression_selects, marker_sets_in

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ROOT: Final[Path] = REPO_ROOT
_UTF_8: Final[str] = "utf-8"

#: The directories the CI contract lane runs. One list, because the three move
#: together through every recipe that names them.
_SCOPE: Final[tuple[str, ...]] = ("dev/ci/tests", "dev/deploy/tests", "dev/release/tests")

_PERF: Final[str] = "perf"
_SERIAL: Final[str] = "serial"

#: Execution markers the marker taxonomy requires exactly one of.
_EXECUTION_MARKERS: Final[frozenset[str]] = frozenset({"unit", "integration", "aeat_live"})

#: A module-level constant naming a calibrated time budget. Matched on the NAME
#: rather than on a measured call, because the call and the assertion are
#: usually many lines apart and often in different functions -- the benchmark
#: this file exists for measures in a fixture and asserts in three separate
#: tests, so a scan anchored on ``time.process_time`` would have found the
#: fixture and reported no test at all.
_BUDGET_CONSTANT: Final[re.Pattern[str]] = re.compile(r"^_?[A-Z][A-Z0-9_]*(?:BUDGET[A-Z0-9_]*|_SECONDS)$")

#: The scheduler argument pinning a run to the controller process.
_NO_WORKERS: Final[str] = "-n0"

#: A justfile recipe header: a lowercase name at column zero, then optional
#: parameters, then a colon.
_RECIPE_HEADER: Final[re.Pattern[str]] = re.compile(r"^(?P<name>[a-z][A-Za-z0-9_-]*)(?:\s[^:]*)?:")


def _budget_constants(tree: ast.Module) -> frozenset[str]:
    """Return the module-level constant names that read as a time budget."""
    names: set[str] = set()
    for statement in tree.body:
        targets: list[ast.expr] = []
        if isinstance(statement, ast.Assign):
            targets = list(statement.targets)
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
        for target in targets:
            if isinstance(target, ast.Name) and _BUDGET_CONSTANT.match(target.id):
                names.add(target.id)
    return frozenset(names)


#: Calls that read a clock. A constant named for seconds is a TIME budget only
#: in a module that measures time -- ``test_ci_workflow.py`` declares
#: ``_HARNESS_WALL_CEILING_SECONDS`` and asserts it against a recipe string and
#: an ini value, which is configuration agreement and not a measurement, so
#: requiring both conditions is what keeps this rule from reporting it.
_CLOCK_READS: Final[frozenset[str]] = frozenset({"process_time", "perf_counter", "monotonic"})

#: The canonical home for load-immune measurement. A module that imports from
#: it is measuring even if it never names a clock itself.
_MEASUREMENT_MODULE: Final[str] = "perf_measurement"


def _module_measures_time(tree: ast.Module) -> bool:
    """Return whether anything in this module reads a clock."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _CLOCK_READS:
            return True
        if isinstance(node, ast.ImportFrom) and node.module is not None and _MEASUREMENT_MODULE in node.module:
            return True
    return False


def _tests_asserting_a_budget(path: Path) -> frozenset[str]:
    """Return the names of tests in ``path`` that assert against a time budget."""
    tree = ast.parse(path.read_text(encoding=_UTF_8))
    budgets = _budget_constants(tree)
    if not budgets or not _module_measures_time(tree):
        return frozenset[str]()
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or not node.name.startswith("test_"):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Assert):
                continue
            if any(isinstance(name, ast.Name) and name.id in budgets for name in ast.walk(inner.test)):
                found.add(node.name)
                break
    return frozenset(found)


def _modules_in_scope() -> tuple[Path, ...]:
    """Return every test module under the CI contract directories."""
    modules: list[Path] = []
    for directory in _SCOPE:
        modules.extend(sorted((_ROOT / directory).glob("test_*.py")))
    return tuple(modules)


def _describe(path: Path) -> str:
    """Name ``path`` relative to the repository, or absolutely when outside it."""
    try:
        return path.relative_to(_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _markers_by_test(path: Path) -> dict[str, frozenset[str]]:
    """Return each test's effective markers in ``path``."""
    markers = marker_sets_in(path)
    assert markers is not None, f"markers could not be read: {path}"
    return {item.test: item.markers for item in markers}


def _unmarked_budget_assertions(modules: tuple[Path, ...]) -> list[str]:
    """Return every budget assertion in ``modules`` that does not carry ``perf``."""
    findings: list[str] = []
    for path in modules:
        asserting = _tests_asserting_a_budget(path)
        if not asserting:
            continue
        markers = _markers_by_test(path)
        relative = _describe(path)
        findings.extend(
            f"{relative}::{test}" for test in sorted(asserting) if _PERF not in markers.get(test, frozenset())
        )
    return findings


@functools.lru_cache(maxsize=1)
def _perf_cohort() -> tuple[tuple[str, frozenset[str]], ...]:
    """Return every ``perf`` test under the CI contract paths, with its markers."""
    cohort: list[tuple[str, frozenset[str]]] = []
    for path in _modules_in_scope():
        relative = _describe(path)
        for test, markers in _markers_by_test(path).items():
            if _PERF in markers:
                cohort.append((f"{relative}::{test}", markers))
    return tuple(sorted(cohort))


def test_no_budget_assertion_here_runs_outside_the_perf_lane() -> None:
    """The gate. A calibrated threshold may only be asserted where perf runs."""
    unmarked = _unmarked_budget_assertions(_modules_in_scope())

    assert unmarked == [], (
        "these tests assert a measured value against a module-level budget constant but do not "
        "carry `perf`, so a per-push lane selects them and the threshold is asserted on a shared "
        "runner:\n  " + "\n  ".join(unmarked)
    )


def test_the_scan_reports_a_budget_assertion_that_lost_its_marker(tmp_path: Path) -> None:
    """Detector teeth, against a written module rather than the live tree.

    The gate above passes on a tree with no budgets at all, so on its own it
    cannot distinguish a clean corpus from a scan that stopped matching. This
    plants the exact defect that reached CI -- a budget constant, an assertion
    against it, and ``serial`` without ``perf`` -- and requires the reader to
    name it.
    """
    module = tmp_path / "test_planted.py"
    module.write_text(
        "import time\n"
        "\n"
        "import pytest\n"
        "\n"
        "_P95_BUDGET_CPU_SECONDS = 3.0\n"
        "\n"
        "\n"
        "@pytest.mark.serial\n"
        "def test_within_budget() -> None:\n"
        "    measured = time.process_time()\n"
        "    assert measured < _P95_BUDGET_CPU_SECONDS\n",
        encoding=_UTF_8,
    )

    assert _tests_asserting_a_budget(module) == frozenset({"test_within_budget"})
    assert _unmarked_budget_assertions((module,)) == [f"{_describe(module)}::test_within_budget"]


def test_the_scan_accepts_the_same_assertion_once_it_carries_perf(tmp_path: Path) -> None:
    """The positive control: the marker is what the gate wants, not silence."""
    module = tmp_path / "test_planted_marked.py"
    module.write_text(
        "import time\n"
        "\n"
        "import pytest\n"
        "\n"
        "_P95_BUDGET_CPU_SECONDS = 3.0\n"
        "\n"
        "\n"
        "@pytest.mark.perf\n"
        "@pytest.mark.serial\n"
        "def test_within_budget() -> None:\n"
        "    measured = time.process_time()\n"
        "    assert measured < _P95_BUDGET_CPU_SECONDS\n",
        encoding=_UTF_8,
    )

    assert _tests_asserting_a_budget(module) == frozenset({"test_within_budget"})
    assert _unmarked_budget_assertions((module,)) == []


def test_a_ratio_between_two_measurements_is_not_reported(tmp_path: Path) -> None:
    """The boundary this file draws, asserted rather than described in prose.

    Two live tests depend on it, so a scan that widened to any timing assertion
    would report both and the remedy would be an exemption list.
    """
    module = tmp_path / "test_ratio.py"
    module.write_text(
        "import time\n"
        "\n"
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.mark.unit\n"
        "def test_warm_is_not_slower_than_cold() -> None:\n"
        "    cold = time.process_time()\n"
        "    warm = time.process_time()\n"
        "    assert warm <= cold * 1.64\n",
        encoding=_UTF_8,
    )

    assert _tests_asserting_a_budget(module) == frozenset()


def test_the_live_perf_cohort_here_is_not_empty() -> None:
    """Anchor: the cohort the placement cases below measure actually exists."""
    assert _perf_cohort(), "no test under the CI contract paths carries `perf`; every case below would be vacuous"


def test_every_perf_test_here_carries_an_execution_marker_and_serial() -> None:
    """Placement: a perf test with no execution marker is selected by no lane."""
    cohort = _perf_cohort()

    unexecutable = sorted(node for node, markers in cohort if not (markers & _EXECUTION_MARKERS))
    parallel = sorted(node for node, markers in cohort if _SERIAL not in markers)

    assert unexecutable == [], (
        "these perf tests carry no execution marker, so every lane's `(unit or integration)` "
        "clause deselects them:\n  " + "\n  ".join(unexecutable)
    )
    assert parallel == [], (
        "these perf tests do not carry `serial`, so a worker-parallel lane could collect them "
        "and a co-resident test would inflate the very measurement they assert:\n  " + "\n  ".join(parallel)
    )


@functools.lru_cache(maxsize=1)
def _worker_pinned_recipes() -> frozenset[str]:
    """Return the recipes whose every pytest invocation pins the controller process.

    ``Lane`` carries what an invocation REACHES and ACCEPTS, not the arguments
    it was written with, so the scheduler pin has to be read from the justfile
    line itself. Read per recipe rather than per line, because a recipe running
    several passes is worker-pinned only if all of them are.
    """
    pinned: set[str] = set()
    unpinned: set[str] = set()
    recipe: str | None = None
    for line in (_ROOT / "justfile").read_text(encoding=_UTF_8).splitlines():
        header = _RECIPE_HEADER.match(line)
        if header is not None:
            name = header.group("name")
            if not isinstance(name, str):
                raise RuntimeError("recipe header did not provide a textual name")
            recipe = name
            continue
        if not line[:1].isspace():
            # A comment between recipes is not part of the one above it. The
            # merge-gate comment block names pytest in prose, and attributing
            # it to the preceding recipe reported that recipe as running an
            # unpinned pass it does not have.
            recipe = None
            continue
        if recipe is None or " pytest " not in f" {line.strip()} ":
            continue
        (pinned if _NO_WORKERS in line.split() else unpinned).add(recipe)
    return frozenset(pinned - unpinned)


def _lanes_over_scope() -> tuple[Lane, ...]:
    """Return every declared lane whose path scope reaches a CI contract directory."""
    return tuple(
        lane
        for lane in declared_lanes(_ROOT)
        if lane.recipe is not None and any(lane.covers_directory(directory) for directory in _SCOPE)
    )


def test_no_lane_over_these_paths_admits_a_perf_test_into_a_parallel_run() -> None:
    """A perf test collected under xdist measures its co-tenants, not the code."""
    pinned = _worker_pinned_recipes()
    selectable = frozenset({_PERF, _SERIAL, "integration"})
    admitting = sorted(
        f"{lane.recipe}: {lane.marker_expression}"
        for lane in _lanes_over_scope()
        if expression_selects(lane.marker_expression, selectable) and lane.recipe not in pinned
    )

    assert admitting == [], f"these lanes select perf tests without pinning {_NO_WORKERS}:\n  " + "\n  ".join(admitting)


def test_some_recipe_selects_the_whole_perf_cohort_here() -> None:
    """A cohort no recipe runs is worse than one that flakes: it reports nothing."""
    cohort = _perf_cohort()
    expected = {node for node, _markers in cohort}
    pinned = _worker_pinned_recipes()
    owners = [
        lane.recipe
        for lane in _lanes_over_scope()
        if lane.recipe in pinned
        and {
            node
            for node, markers in cohort
            if lane.covers(node.split("::")[0]) and expression_selects(lane.marker_expression, markers)
        }
        == expected
    ]

    assert owners, (
        f"no {_NO_WORKERS} recipe selects every perf test under the CI contract paths; the cohort "
        f"would be collected by nothing or split across lanes: {sorted(expected)}"
    )
