"""Calc-grade settlement advisory: a manual terminal liquidación casilla advises.

A settlement-bearing revision whose terminal liquidación casilla is
``input_kind = "manual"`` (the calc chain models the inputs but not the final
liquidación) surfaces a non-blocking advisory on the calculate path; a revision
that computes its settlement raises none. Every Modelo 100 year of the published
support envelope is checked. The assertions read the LOADED snapshot's casilla
``input_kind`` (structural) and cross-check the collector against it --
non-tautological, no formula output, no mocks.
"""

from __future__ import annotations

from functools import cache

import pytest

from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from .._settlement_grade_advisory import collect_settlement_not_computed_diagnostics
from ..settlement_casilla import SETTLEMENT_SEMANTIC_ROLES

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return support.years


def _revision(modelo: str, year: int, period: str):
    return published_snapshot(modelo, filing_year=year, period=period).revision


def _settlement_casillas(revision):
    return [casilla for casilla in revision.casillas if casilla.semantic_role in SETTLEMENT_SEMANTIC_ROLES]


@pytest.mark.parametrize("year", _supported_years())
def test_advises_exactly_the_manual_settlement_casillas_m100(year: int) -> None:
    """The collector flags exactly the settlement-role casillas the edition leaves uncomputed.

    The expected set is computed from the revision independently of the
    collector, so the test fails if the collector over- or under-fires; an
    edition that computes its settlement must raise no advisory at all.
    """
    revision = _revision("100", year, "0A")
    settlement = _settlement_casillas(revision)
    assert settlement, f"fixture sanity: M100 {year} must carry settlement-role casillas"
    expected_ids = {casilla.id for casilla in settlement if str(casilla.input_kind) != "computed"}

    diagnostics = collect_settlement_not_computed_diagnostics(revision)

    assert {d.casilla_id for d in diagnostics} == expected_ids
    assert all(d.reason == "settlement_not_computed" for d in diagnostics)
    assert all(d.source_kind == "settlement_casilla" for d in diagnostics)


def test_the_envelope_exercises_a_computed_settlement() -> None:
    """At least one supported edition computes its settlement, so the no-advisory path is covered."""
    computed_years = [
        year
        for year in _supported_years()
        if all(str(casilla.input_kind) == "computed" for casilla in _settlement_casillas(_revision("100", year, "0A")))
    ]
    assert computed_years
    for year in computed_years:
        assert collect_settlement_not_computed_diagnostics(_revision("100", year, "0A")) == ()


def test_no_advisory_for_revision_without_a_settlement_role_casilla() -> None:
    """M303 carries no M100 terminal-settlement role casilla → no advisory (out of scope)."""
    floor = _supported_years()[0]
    assert collect_settlement_not_computed_diagnostics(_revision("303", floor, "2T")) == ()
