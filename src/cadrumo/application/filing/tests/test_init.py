"""Registry-loaded input-kind invariants used by the filing layer."""

from __future__ import annotations

import pytest

from ....core.resources import resources
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _authority():
    return resources().modelos.authority


def test_formula_backed_casillas_are_computed_inputs() -> None:
    authority = _authority()
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")

    formula_casillas = [casilla for casilla in snapshot.revision.casillas if casilla.formula is not None]

    assert formula_casillas, "modelo 130 must keep formula-backed casillas in the committed registry"
    assert all(casilla.input_kind is InputKind.COMPUTED for casilla in formula_casillas)


def test_binding_backed_casillas_are_bound_inputs() -> None:
    authority = _authority()
    snapshot = authority.snapshot("303", filing_year=2026, period="1T")

    bound_casillas = [casilla for casilla in snapshot.revision.casillas if casilla.binding is not None]

    assert bound_casillas, "modelo 303 must keep binding-backed casillas in the committed registry"
    assert all(casilla.input_kind is InputKind.BOUND for casilla in bound_casillas)


def test_filing_period_metadata_casillas_are_informational_inputs() -> None:
    authority = _authority()
    snapshot = authority.snapshot("303", filing_year=2026, period="1T")

    period_casillas = [casilla for casilla in snapshot.revision.casillas if casilla.semantic_role == "filing_period"]

    assert period_casillas, "modelo 303 must declare filing-period metadata casillas"
    assert all(casilla.input_kind is InputKind.INFORMATIONAL for casilla in period_casillas)
