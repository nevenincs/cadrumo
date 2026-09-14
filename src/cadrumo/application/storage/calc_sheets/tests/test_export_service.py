"""Application-owned calc-sheets export orchestration contracts.

These tests cover the renderer-neutral plan and coverage metadata without
constructing or importing any outbound transport or persistence adapter. The
adapter-backed failure-path integration lives with the Google outbound tests.
"""

from __future__ import annotations

from datetime import date

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ..engine import build_export_plan
from ..export_service import _export_scope_description, _SingleExportCoverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m130_plan():
    snapshot = compiled_bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


class TestSingleExportCoverage:
    """The coverage source's contract: one unit, no divergence concept."""

    def test_a_reached_export_counts_one_unit_and_no_divergences(self) -> None:
        coverage = _SingleExportCoverage(reached=True)
        assert coverage.reached_count == 1
        assert coverage.divergences == ()

    def test_an_unreached_export_counts_zero(self) -> None:
        coverage = _SingleExportCoverage(reached=False)
        assert coverage.reached_count == 0
        assert coverage.divergences == ()


def test_scope_description_names_modelo_period_and_year() -> None:
    plan = _m130_plan()
    scope = _export_scope_description(plan)
    assert plan.metadata.modelo_id in scope
    assert plan.metadata.period.registry_token in scope
    assert str(plan.metadata.filing_year) in scope
