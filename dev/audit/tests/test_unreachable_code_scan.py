"""The reachability gate that walks the real shipped tree.

Reads the real ``pyproject.toml`` console scripts and parses every shipped
module under ``src/cadrumo``, so this is ``integration``: it proves the
scanner against the live tree rather than a synthetic one. The
classification and rendering checks live in ``test_unreachable_code``.
"""

from __future__ import annotations

import pytest

from ..._paths import REPO_ROOT
from ..unreachable_code import ModuleReach, UnreachableCodeOutcome, run_unreachable_code_scan

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def test_real_scan_over_the_tree_returns_a_typed_outcome_with_real_findings() -> None:
    """A real scan classifies to CLEAN or FINDINGS, never a crash, and names real paths.

    No self-skip on a clean tree (forbidden by ``test_no_skip_xfail``): both
    branches are asserted inside one test, matching the vulture gate.
    """
    result = run_unreachable_code_scan(_REPO_ROOT)

    assert result.outcome in {UnreachableCodeOutcome.CLEAN, UnreachableCodeOutcome.FINDINGS}, result.reason
    assert result.headline()
    assert set(result.roots) >= {"cadrumo.entrypoints._cli_main:main", "cadrumo.entrypoints.tui.launcher:main"}
    assert 0 < result.reachable_modules <= result.shipped_modules

    reported_modules = {finding.module for finding in result.modules}
    assert reported_modules.isdisjoint({"cadrumo", "cadrumo.entrypoints._cli_main", "cadrumo.entrypoints.tui.launcher"})

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
