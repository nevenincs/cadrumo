"""Detector teeth for live zero-target unreachable-module coverage."""

from __future__ import annotations

import pytest

from dev.audit.unreachable_code import ModuleFinding, ModuleReach, UnreachableCodeResult

from ..unreachable_module_coverage import evaluate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _result(*findings: ModuleFinding) -> UnreachableCodeResult:
    return UnreachableCodeResult.from_findings(
        roots=("pkg.cli:main",),
        shipped_modules=len(findings) + 1,
        reachable_modules=1,
        modules=tuple(findings),
        symbols=(),
    )


@pytest.mark.parametrize("reach", tuple(ModuleReach))
def test_every_non_command_reached_category_stays_red(reach: ModuleReach) -> None:
    finding = ModuleFinding(
        path="src/pkg/stranded.py",
        module="pkg.stranded",
        reach=reach,
        spanned_modules=1,
        used_by=(),
    )

    verdict = evaluate(_result(finding))

    assert not verdict.is_clean
    assert "pkg.stranded" in verdict.report()
    assert reach.value in verdict.report()


def test_an_empty_live_set_is_green() -> None:
    result = UnreachableCodeResult.clean(
        roots=("pkg.cli:main",),
        shipped_modules=1,
        reachable_modules=1,
    )

    verdict = evaluate(result)

    assert verdict.is_clean
    assert verdict.report() == "unreachable-module coverage: no findings"
