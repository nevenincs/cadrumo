"""The reachability gate that walks the real shipped tree.

Reads the real ``pyproject.toml`` console scripts and parses every shipped
module under ``src/cadrumo``, so this is ``integration``: it proves the
scanner against the live tree rather than a synthetic one. The
classification and rendering checks live in ``test_unreachable_code``.
"""

from __future__ import annotations

import pytest

from dev._paths import REPO_ROOT

from ..unreachable_code import ModuleReach, UnreachableCodeOutcome, run_unreachable_code_scan

# One real scan walks every shipped, test and tooling module; the ceiling is the
# one the sibling whole-tree scans carry, not the per-unit-test default.
pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.timeout(900)]

_REPO_ROOT = REPO_ROOT


def test_real_scan_over_the_tree_returns_a_typed_outcome_with_real_findings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real scan classifies to CLEAN or FINDINGS, never a crash, and names real paths.

    No self-skip on a clean tree (forbidden by ``test_no_skip_xfail``): both
    branches are asserted inside one test, matching the vulture gate.

    The same scan also proves the reference walk read every file. If that ever
    fails, the findings were computed over a corpus missing the named files, and
    the run should be repeated rather than acted on.
    """
    result = run_unreachable_code_scan(_REPO_ROOT)

    # The absence claim below is satisfied by an EMPTY stderr, so a scan that
    # read nothing at all - a mis-resolved root, a walk that short-circuits -
    # reports exactly as clean as a healthy one. The result carries how much
    # was actually walked and was discarded. Floors, not pinned counts: live
    # the scan sees 2,108 shipped modules across 4 roots.
    assert result.roots, result
    assert result.shipped_modules > 1500, result.shipped_modules
    assert result.reachable_modules > 1500, result.reachable_modules
    assert "were unreadable during the reference walk" not in capsys.readouterr().err

    assert result.outcome in {UnreachableCodeOutcome.CLEAN, UnreachableCodeOutcome.FINDINGS}, result.reason
    assert result.headline()
    assert "cadrumo.entrypoints.cli.bootstrap:main" in set(result.roots)
    assert "cadrumo.entrypoints.tui.__main__ (python -m)" in set(result.roots)
    assert 0 < result.reachable_modules <= result.shipped_modules

    reported_modules = {finding.module for finding in result.modules}
    assert reported_modules.isdisjoint({"cadrumo", "cadrumo.entrypoints.cli.bootstrap"})

    if result.outcome is UnreachableCodeOutcome.FINDINGS:
        for module in result.modules:
            target = _REPO_ROOT / module.path
            assert target.is_dir() if module.is_package else target.is_file(), f"unknown path: {module.path}"
            assert module.reach in set(ModuleReach)
            assert module.spanned_modules >= 1
            assert "/tests/" not in f"/{module.path}"
        for symbol in result.symbols:
            assert (_REPO_ROOT / symbol.path).is_file(), f"unknown path: {symbol.path}"
            assert symbol.line > 0
            assert symbol.qualname.endswith(symbol.name)
