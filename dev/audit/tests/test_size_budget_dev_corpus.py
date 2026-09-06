"""Gate: the size budget measures `dev/` too, and the dashboard carries the result.

`dev/` sat outside every size axis until it produced a 6,060-line quality module
in two days. The scanner that should have seen it existed the whole time and was
correct; it measured the shipped package only, and the pytest gate enforcing it
had been deleted when the package's zero-awareness boundary was closed. Nothing
ran it, so nothing said anything.

Two properties therefore need holding, and neither is implied by the other:

* the `dev/` tree is IN the measured corpus, so growth there is visible at all;
* the composed advisory dashboard CARRIES the dimension, so the measurement
  reaches a surface somebody reads.

The corpus assertion is deliberately anchored to a real oversize module rather
than to a count. A count moves every time somebody splits a file and would have
to be edited to stay green, which is the decay mode the size baseline itself was
regenerated to escape.
"""

from __future__ import annotations

import inspect

import pytest

from ..advisory import audit_size_budget, build_advisory_report
from ..size_budget import (
    SizeBudgetResult,
    dev_python_files,
    measure_dev_module_lines,
    run_size_budget_scan,
)

pytestmark = [pytest.mark.hex_core]

# The corpus enumeration is cheap and stays on the fast per-push lane. The three
# tests that need a full measurement are marked `integration`: one scan reads
# ~6,800 modules and AST-parses ~16,000 callables, which is a minute the
# per-push unit lane should not spend. `just test-dev-tooling` selects both
# markers, so nothing drops out of coverage by being moved off the fast lane.


@pytest.fixture(scope="module")
def scan() -> SizeBudgetResult:
    """One scan shared by every test that needs it.

    The scan measures ~6,800 modules and ~16,000 callables and costs roughly a
    minute. Re-running it per test put this file near the 300-second per-test
    ceiling for no added coverage: the corpus does not change between
    assertions in one session.
    """
    return run_size_budget_scan()


@pytest.mark.unit
def test_the_dev_tree_is_enumerated_without_compiled_caches() -> None:
    """The corpus is real `dev/` source, and never a stale `__pycache__` artefact."""
    files = dev_python_files()

    assert files, "dev/ must not enumerate empty; an empty corpus measures nothing"
    assert all(path.suffix == ".py" for path in files)
    assert not [path for path in files if "__pycache__" in path.parts]


@pytest.mark.unit
def test_dev_modules_are_measured_against_the_repository_root() -> None:
    """Keys are repo-relative POSIX paths, so `dev/` and `src/` share one namespace."""
    measured = measure_dev_module_lines()

    assert measured
    assert all(key.startswith("dev/") for key in measured)
    assert all("\\" not in key for key in measured)


@pytest.mark.integration
def test_an_oversize_dev_module_is_a_finding(scan: SizeBudgetResult) -> None:
    """The defect this corpus exists for: `dev/` growth must reach the verdict.

    Anchored to whichever `dev/` module is largest rather than to a named file
    or a count, so the test keeps its meaning after the current offenders are
    split and cannot be satisfied by editing a number.
    """
    measured = measure_dev_module_lines()
    largest = max(measured, key=lambda key: measured[key])
    if measured[largest] <= 1250:
        pytest.skip("no dev/ module exceeds the default module limit; nothing to prove here")

    findings = scan.modules.failing

    assert any(line.startswith(f"{largest}:") for line in findings), (
        f"{largest} is {measured[largest]} lines and must appear in the size-budget verdict"
    )


@pytest.mark.integration
def test_the_scan_spans_both_trees(scan: SizeBudgetResult) -> None:
    """A regression that dropped either tree would still look like a working scan."""
    findings = scan.modules.failing
    prefixes = {line.split("/", 1)[0] for line in findings}

    assert "dev" in prefixes
    assert "src" in prefixes


@pytest.mark.integration
def test_the_dimension_reports_amber_rather_than_green_while_debt_stands(scan: SizeBudgetResult) -> None:
    """An unmeasurable or ignored axis must never render as GREEN."""
    dimension = audit_size_budget()

    assert dimension.report.name == "size_budget"
    assert dimension.report.status.value == ("green" if scan.is_clean else "amber")
    assert len(dimension.report.details or []) == len(scan.findings)


@pytest.mark.unit
def test_the_composed_dashboard_carries_the_size_budget_dimension() -> None:
    """The measurement must reach the surface people actually read.

    Asserted structurally rather than by running the composition: the other
    dimensions shell out to semgrep and a full dead-code walk, so executing it
    here would put minutes into the unit lane to prove one call site. What
    matters is that `build_advisory_report` is the caller, which the source
    settles.
    """
    source = inspect.getsource(build_advisory_report)

    assert "audit_size_budget()" in source
