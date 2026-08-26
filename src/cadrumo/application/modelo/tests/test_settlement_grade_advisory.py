"""Calc-grade settlement advisory (#24-A): a manual terminal liquidación casilla advises.

A settlement-bearing revision whose terminal liquidación casilla is
``input_kind = "manual"`` (the calc chain models the inputs but not the final
liquidación) surfaces a non-blocking advisory on the calculate path -- M100
2020-2023 are the live case; M100 2025 computes the settlement (no advisory). The
assertions read the LOADED snapshot's casilla ``input_kind`` (structural) and
cross-check the collector against it -- non-tautological, no formula output, no
mocks. The structural complement to the value-level settlement predicate (#24-B/#38).
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from .._settlement_grade_advisory import (
    SETTLEMENT_SEMANTIC_ROLES,
    collect_settlement_not_computed_diagnostics,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _revision(modelo: str, year: int, period: str):
    return bundled_authority().snapshot(modelo, filing_year=year, period=period).revision


@pytest.mark.parametrize("year", [2020, 2023])
def test_advises_exactly_the_manual_settlement_casillas_m100(year: int) -> None:
    """M100 2020/2023 leave the settlement casillas manual (with a formula chain) → advise.

    The flagged casilla set must equal exactly the settlement-role casillas whose
    ``input_kind`` is not ``computed`` -- computed from the revision independently
    of the collector, so the test fails if the collector over- or under-fires.
    """
    revision = _revision("100", year, "0A")
    expected_ids = {
        casilla.id
        for casilla in revision.casillas
        if casilla.semantic_role in SETTLEMENT_SEMANTIC_ROLES and str(casilla.input_kind) != "computed"
    }
    assert expected_ids, f"fixture sanity: M100 {year} must carry manual settlement casillas"

    diagnostics = collect_settlement_not_computed_diagnostics(revision)

    assert {d.casilla_id for d in diagnostics} == expected_ids
    assert all(d.reason == "settlement_not_computed" for d in diagnostics)
    assert all(d.source_kind == "settlement_casilla" for d in diagnostics)


def test_no_advisory_when_m100_settlement_is_computed_2025() -> None:
    """M100 2025 computes the settlement (input_kind == computed) → no advisory."""
    revision = _revision("100", 2025, "0A")
    # fixture sanity: the settlement casillas ARE computed on 2025.
    assert any(
        casilla.semantic_role in SETTLEMENT_SEMANTIC_ROLES and str(casilla.input_kind) == "computed"
        for casilla in revision.casillas
    )
    assert collect_settlement_not_computed_diagnostics(revision) == ()


def test_no_advisory_for_revision_without_a_settlement_role_casilla() -> None:
    """M303 carries no M100 terminal-settlement role casilla → no advisory (out of scope)."""
    assert collect_settlement_not_computed_diagnostics(_revision("303", 2022, "2T")) == ()
