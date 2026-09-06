"""Gate: the size budget measures `dev/`, and the ratchet detects what it claims to.

`dev/` sat outside every size axis while the shipped package was measured, so a
development module could accrete without bound and no check anywhere would say
so. The corpus half of this file proves `dev/` is measured at all; the ratchet
half proves the measurement has teeth.

Every assertion here is STATE-INDEPENDENT. An earlier version asserted that both
trees currently contain failing modules, which made paying the debt down turn the
suite red -- a gate punishing the remedy it exists to motivate. The properties
below hold whether the tree is clean or filthy: that each tree is measured, that
a broken walk refuses rather than reading clean, and that a subject crossing its
own ceiling fails.

The detector proofs run against a temporary tree rather than live findings.
`scan_module_lines` takes its files and root as parameters precisely so the real
measurement code can be pointed at one, so each proof exercises production code
without depending on the repository's current debt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.tests import MODULE_POLICY, build_limits, evaluate_budget, scan_module_lines
from cadrumo.tests.size_budget import EmptyScanError

from ..size_budget import (
    dev_python_files,
    load_size_budget_baseline,
    measure_dev_module_lines,
    run_size_budget_scan,
)

pytestmark = [pytest.mark.hex_core]

_OVER = MODULE_POLICY.default_limit + 500


def _planted(root: Path, relative: str, lines: int) -> Path:
    """Write a module of exactly ``lines`` lines into a temporary tree."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x = 1\n" * lines, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The dev/ corpus is measured at all
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_dev_tree_is_enumerated_without_compiled_caches() -> None:
    """The corpus is real `dev/` source, never a stale `__pycache__` artefact."""
    files = dev_python_files()

    assert files, "dev/ must not enumerate empty; an empty corpus measures nothing"
    assert all(path.suffix == ".py" for path in files)
    assert not [path for path in files if "__pycache__" in path.parts]


@pytest.mark.unit
def test_dev_modules_are_measured_against_the_repository_root() -> None:
    """Keys are repo-relative POSIX paths, so `dev/` and `src/` share one namespace.

    A statement about the CORPUS, not about findings: it holds identically
    whether or not any `dev/` module is currently oversize.
    """
    measured = measure_dev_module_lines()

    assert measured
    assert all(key.startswith("dev/") for key in measured)
    assert all("\\" not in key for key in measured)


# ---------------------------------------------------------------------------
# The ratchet detects what it claims to
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_module_crossing_its_own_ceiling_is_reported(tmp_path: Path) -> None:
    """THE defect: a declared subject that keeps growing must fail.

    This is the shape of the incident that motivated measuring `dev/` at all --
    a module accreting past a size somebody already accepted. A ceiling-less
    model passes it once the subject is known, so it is proved explicitly, at
    one line over.
    """
    planted = _planted(tmp_path, "dev/quality/grower.py", _OVER)
    measured = scan_module_lines(files=(planted,), root=tmp_path)

    verdict = evaluate_budget(measured, {"dev/quality/grower.py": _OVER - 1}, MODULE_POLICY)

    assert verdict.over_budget == (f"dev/quality/grower.py: {_OVER} lines > limit {_OVER - 1}",)
    assert verdict.failing


@pytest.mark.unit
def test_an_undeclared_oversize_module_is_reported(tmp_path: Path) -> None:
    """A module nothing has ever declared is measured against the default."""
    planted = _planted(tmp_path, "dev/quality/newcomer.py", _OVER)
    measured = scan_module_lines(files=(planted,), root=tmp_path)

    verdict = evaluate_budget(measured, {}, MODULE_POLICY)

    assert verdict.over_budget == (f"dev/quality/newcomer.py: {_OVER} lines > limit {MODULE_POLICY.default_limit}",)


@pytest.mark.unit
def test_a_subject_inside_its_ceiling_is_clean(tmp_path: Path) -> None:
    """The gate stays quiet on a declared subject that has not moved."""
    planted = _planted(tmp_path, "dev/quality/steady.py", _OVER)
    measured = scan_module_lines(files=(planted,), root=tmp_path)

    verdict = evaluate_budget(measured, {"dev/quality/steady.py": _OVER}, MODULE_POLICY)

    assert not verdict.failing


@pytest.mark.unit
def test_regeneration_cannot_launder_a_live_offender(tmp_path: Path) -> None:
    """Re-measuring must not lift a ceiling the subject has already broken.

    The anti-launder rule is what stops the ratchet being reset by whoever
    caused the growth: without it, regenerating after an accretion simply
    blesses it, and the gate reports green on the defect it exists to catch.
    """
    planted = _planted(tmp_path, "dev/quality/grower.py", _OVER)
    measured = scan_module_lines(files=(planted,), root=tmp_path)
    broken = {"dev/quality/grower.py": _OVER - 1}

    held = build_limits(measured, MODULE_POLICY, previous=broken, accept_growth=False)
    absorbed = build_limits(measured, MODULE_POLICY, previous=broken, accept_growth=True)

    assert held["dev/quality/grower.py"] == _OVER - 1, "a live offender keeps its broken ceiling"
    assert evaluate_budget(measured, held, MODULE_POLICY).failing, "and stays red"
    assert absorbed["dev/quality/grower.py"] >= _OVER, "only the explicit flag may absorb it"


# ---------------------------------------------------------------------------
# The guards refuse rather than reading clean
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_broken_dev_walk_refuses_rather_than_reporting_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty dev walk must raise, not report a clean dev axis.

    The two trees are unioned before the shared corpus floor is applied, and
    `src/` alone clears that floor several times over. Without a floor of its
    own the dev axis could return nothing, contribute no findings, and read as
    healthy -- absent and zero collapsed into one.
    """
    monkeypatch.setattr("dev.audit.size_budget.dev_python_files", lambda: ())

    with pytest.raises(EmptyScanError, match="dev source walk is broken"):
        measure_dev_module_lines()


# ---------------------------------------------------------------------------
# The live tree
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_the_live_tree_sits_inside_its_committed_baseline() -> None:
    """The real gate: every subject is inside the band the baseline declares."""
    result = run_size_budget_scan()

    assert result.is_clean, "\n".join(result.findings)


@pytest.mark.integration
def test_the_committed_baseline_declares_both_measured_trees() -> None:
    """Debt is declared for both trees, so neither axis is silently absent."""
    baseline = load_size_budget_baseline()
    prefixes = {key.split("/", 1)[0] for key in baseline.modules}

    assert baseline.modules, "the committed baseline must not be empty"
    assert prefixes <= {"src", "dev"}
