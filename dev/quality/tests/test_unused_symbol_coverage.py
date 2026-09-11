"""Detector teeth for live zero-target exact symbol coverage."""

from __future__ import annotations

import pytest

from dev.audit.unreachable_code import SymbolFinding, SymbolKind, UnreachableCodeResult
from dev.audit.unreachable_code import TestFinding as OrphanTestFinding

from ..unused_symbol_coverage import from_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_an_exact_symbol_and_orphaned_test_are_both_reported() -> None:
    symbol = SymbolFinding(
        path="src/pkg/live.py",
        line=3,
        kind=SymbolKind.FUNCTION,
        name="stranded",
        qualname="stranded",
        used_by=(),
        module="pkg.live",
    )
    orphan = OrphanTestFinding(
        path="src/pkg/tests/test_live.py",
        module="pkg.tests.test_live",
        subjects=("pkg.live:stranded",),
    )
    result = UnreachableCodeResult.from_findings(
        roots=("pkg.cli:main",),
        shipped_modules=2,
        reachable_modules=2,
        modules=(),
        symbols=(symbol,),
        tests=(orphan,),
    )

    verdict = from_result(result)

    assert not verdict.is_clean
    assert "pkg.live:stranded" in verdict.report()
    assert "test:pkg.tests.test_live" in verdict.report()


def test_an_empty_live_set_is_green() -> None:
    result = UnreachableCodeResult.clean(roots=("pkg.cli:main",), shipped_modules=1, reachable_modules=1)
    assert from_result(result).is_clean
