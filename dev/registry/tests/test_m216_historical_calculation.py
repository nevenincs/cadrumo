"""Historical BOE 216 arithmetic through the real snapshot and calculation engine."""

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.errors import CasillaConstraintViolationError, RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, open_ended_revision

from ..compiler.authority import compiled_bundled_authority

# The closed edition BOE 216 printed its subtraction under, and the last exercise it governs.
_HISTORICAL = authored_revisions("216")[0]
_HISTORICAL_ID = str(_HISTORICAL.id)
assert _HISTORICAL.valid_to is not None
_YEAR = _HISTORICAL.valid_to.year

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _calculate(inputs):
    authority = compiled_bundled_authority()
    snapshot = authority.snapshot(
        "216", filing_year=_YEAR, period="4T", revision_id=_HISTORICAL_ID, grade=RegistryAuthorityGrade.CALCULATION
    )
    with validating_governed_facts(authority):
        return calculate_registry_snapshot(snapshot, inputs=inputs, date_context={"filing_period": date(_YEAR, 12, 31)})


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
        compiled_bundled_authority().snapshot("216", filing_year=_YEAR, period="4T", revision_id=_HISTORICAL_ID)


def test_current_formula_keeps_current_casilla_references():
    revision = compiled_bundled_authority().modelo("216").revisions[str(open_ended_revision("216").id)]
    formula = next(f for f in revision.formulas if f.id == "modelo-216-resultado")
    assert str(formula.target_casilla_id) == "21"
    assert [str(a.casilla_id) for a in formula.expression.args] == ["13", "20"]
    assert len(revision.formulas) == 6
    assert "boe-2008-18497-modelo-216-calculation-guidance" not in formula.source_refs
