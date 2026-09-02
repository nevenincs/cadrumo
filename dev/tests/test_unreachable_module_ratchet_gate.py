"""Ratchet gate: the shipped tree's unreachable-module set matches its baseline.

Wires :mod:`dev.quality.unreachable_module_ratchet` into the pytest/CI surface.

The gate it protects is a population, not a direction, and the distinction is
why it earns a place beside the existing import-direction gate in
``cadrumo.tests.test_production_never_imports_test_support``. A test-support
helper written into a product namespace imports nothing from the test tree, so
the direction gate is structurally blind to it; what gives it away is that no
declared entrypoint can reach it. That is this gate's subject.

Both failure directions carry their own control, because they share no code
path and each was silently vacuous at some point during construction: a
regression check that cannot see a new module, and a stale check that never
fires, both look exactly like a clean tree. So the synthetic cases below prove
a planted defect IS reported and that its healthy neighbour is NOT, and the
frozen-prefix case proves the carve-out suppresses both directions rather than
only the one it was written for.

The defects are planted in a throwaway ``tmp_path`` tree built from outside the
repository. No production module is monkeypatched and the contributor's working
tree is never mutated, so a crashed run leaves no residue and a peer's sweep
cannot commit the plant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..audit.unreachable_code import EntryPoint, ShippedTreeSpec, scan_unreachable_code
from ..quality.unreachable_module_ratchet import (
    BASELINE_PATH,
    UnreachableBaseline,
    evaluate,
    run_gate,
    unreachable_modules,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_EXCLUDES = ("src/pkg/tests", "src/pkg/tests/**", "src/pkg/**/tests", "src/pkg/**/tests/**")


def _write(root: Path, relative: str, text: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _planted_tree(root: Path) -> ShippedTreeSpec:
    """A package whose entrypoint reaches ``live`` and never reaches ``stranded``."""
    _write(root, "src/pkg/__init__.py")
    _write(root, "src/pkg/cli.py", "from .live import go\n\n\ndef main() -> None:\n    go()\n")
    _write(root, "src/pkg/live.py", "def go() -> None: ...\n")
    _write(root, "src/pkg/stranded.py", "def helper() -> None: ...\n")
    _write(root, "src/pkg/deferred/__init__.py")
    _write(root, "src/pkg/deferred/screen.py", "def render() -> None: ...\n")
    return ShippedTreeSpec(
        repo_root=root,
        src_root=root / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=_EXCLUDES,
    )


@pytest.fixture
def planted(tmp_path: Path) -> ShippedTreeSpec:
    return _planted_tree(tmp_path)


def test_the_live_shipped_tree_matches_its_committed_baseline() -> None:
    """The real gate. A regression or a stale entry fails here with the module named."""
    verdict = run_gate()

    assert verdict.is_clean, verdict.report()


def test_the_committed_baseline_names_only_modules_the_tree_still_reports() -> None:
    """A baseline entry that no longer corresponds to anything is the stale direction.

    Asserted separately from the combined verdict so a stale entry cannot be
    read as a regression when the gate fails.
    """
    verdict = run_gate()

    assert verdict.stale == (), f"paid-down entries still in {BASELINE_PATH.name}: {verdict.stale}"


def test_a_new_unreachable_module_is_reported_as_a_regression(planted: ShippedTreeSpec) -> None:
    """A module the entrypoint cannot reach, absent from the baseline, fails the gate."""
    result = scan_unreachable_code(planted)
    baseline = UnreachableBaseline(allowed=frozenset(), frozen_prefixes=())

    verdict = evaluate(result, baseline)

    assert "pkg.stranded" in verdict.regressions
    assert not verdict.is_clean


def test_the_reachable_neighbour_is_not_reported(planted: ShippedTreeSpec) -> None:
    """The control: the module the entrypoint DOES reach is never a finding.

    Without this the regression check above would pass just as happily if the
    scan reported every module in the tree.
    """
    result = scan_unreachable_code(planted)

    reported = unreachable_modules(result)

    assert "pkg.stranded" in reported
    assert "pkg.live" not in reported
    assert "pkg.cli" not in reported


def test_a_baselined_module_passes_while_it_remains_unreachable(planted: ShippedTreeSpec) -> None:
    """An accepted entry is not a failure; that is what makes the backlog workable."""
    result = scan_unreachable_code(planted)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.stranded", "pkg.deferred"}),
        frozen_prefixes=(),
    )

    verdict = evaluate(result, baseline)

    assert verdict.is_clean, verdict.report()


def test_a_paid_down_baseline_entry_is_reported_as_stale(planted: ShippedTreeSpec) -> None:
    """Naming a module the tree no longer reports fails, so the baseline cannot rot."""
    result = scan_unreachable_code(planted)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.stranded", "pkg.deferred", "pkg.already_deleted"}),
        frozen_prefixes=(),
    )

    verdict = evaluate(result, baseline)

    assert verdict.stale == ("pkg.already_deleted",)
    assert not verdict.is_clean


def test_a_frozen_prefix_is_excluded_in_both_directions(planted: ShippedTreeSpec) -> None:
    """A deferred cluster neither has to be baselined nor has to persist.

    Both directions are asserted together: the cluster is reported by the audit
    yet absent from ``allowed`` (which would otherwise be a regression), and
    ``allowed`` names a member that is gone (which would otherwise be stale).
    """
    result = scan_unreachable_code(planted)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.stranded", "pkg.deferred.retired_screen"}),
        frozen_prefixes=("pkg.deferred",),
    )

    verdict = evaluate(result, baseline)

    assert verdict.is_clean, verdict.report()
    assert "pkg.deferred" in verdict.frozen


def test_an_unscannable_tree_refuses_rather_than_reporting_clean(tmp_path: Path) -> None:
    """A gate that cannot see the tree must fail loudly, not pass by default."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/cli.py", "def main(:\n")
    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=_EXCLUDES,
    )
    baseline_path = tmp_path / "absent_baseline.toml"

    with pytest.raises(RuntimeError, match="ratchet unproven"):
        run_gate(tmp_path, baseline_path=baseline_path)

    assert not spec.entry_points[0].attribute == ""
