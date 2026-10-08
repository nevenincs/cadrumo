"""Historical BOE 216 arithmetic through the real snapshot and calculation engine."""

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.errors import CasillaConstraintViolationError, RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _calculate(inputs):
    authority = compiled_bundled_authority()
    snapshot = authority.snapshot(
        "216", filing_year=2023, period="4T", revision_id="2020-2023", grade=RegistryAuthorityGrade.CALCULATION
    )
    with validating_governed_facts(authority):
        return calculate_registry_snapshot(snapshot, inputs=inputs, date_context={"filing_period": date(2023, 12, 31)})


@pytest.mark.parametrize(
    "withheld,prior,expected", [("1900", "100", "1800"), ("0", "0", "0"), ("1900.37", "100.12", "1800.25")]
)
def test_historical_result_matches_the_printed_subtraction(withheld, prior, expected):
    result = _calculate({"3": Decimal(withheld), "6": Decimal(prior)})
    assert result.values["7"] == Decimal(expected)
    observation = next(o for o in result.observations if o.casilla_id == "7")
    assert observation.operand_casilla_refs == ("3", "6")
    assert "boe-2008-18497-modelo-216-calculation-guidance" in observation.source_refs


@pytest.mark.parametrize("supplied_result", ["0", "9999"])
def test_computed_result_cannot_be_overridden_by_an_input(supplied_result):
    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied"):
        _calculate({"3": Decimal("1900"), "6": Decimal("100"), "7": Decimal(supplied_result)})


def test_negative_result_is_rejected_without_clamping():
    with pytest.raises(CasillaConstraintViolationError):
        _calculate({"3": Decimal("100"), "6": Decimal("1900")})


def test_nonwithheld_income_cannot_change_the_payable_amount():
    result = _calculate({"3": Decimal("1900"), "6": Decimal("100"), "4": Decimal("999"), "5": Decimal("999999")})
    assert result.values["7"] == Decimal("1800")


def test_historical_calculation_does_not_grant_filing_grade():
    with pytest.raises(RegistryValidationError, match="cannot satisfy the requested 'filing'"):
        compiled_bundled_authority().snapshot("216", filing_year=2023, period="4T", revision_id="2020-2023")


def test_current_formula_keeps_current_casilla_references():
    revision = compiled_bundled_authority().modelo("216").revisions["2024-y-siguientes"]
    formula = next(f for f in revision.formulas if f.id == "modelo-216-resultado")
    assert str(formula.target_casilla_id) == "21"
    assert [str(a.casilla_id) for a in formula.expression.args] == ["13", "20"]
    assert len(revision.formulas) == 6
    assert "boe-2008-18497-modelo-216-calculation-guidance" not in formula.source_refs
