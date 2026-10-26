"""A failed formula precondition is never an amount or an invented dependency."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..errors import RegistryValidationError
from ..formula_runtime import evaluate_expression
from ..schema_formula import FormulaExpression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _expression():
    return FormulaExpression(
        op="require_condition", args=(FormulaExpression(binding="valid"), FormulaExpression(binding="amount"))
    )


def _evaluate(values, *, booleans=None, expression=None, refs=None):
    return evaluate_expression(
        expression or _expression(),
        values={},
        binding_values=values,
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=refs if refs is not None else [],
        operand_casilla_refs=[],
        operand_values=[],
        boolean_binding_values=booleans,
    )


def test_false_precondition_does_not_read_missing_amount_or_fabricate_zero():
    refs = []
    with pytest.raises(RegistryValidationError, match=r"^formula precondition was not satisfied$") as error:
        _evaluate({"valid": Decimal(0)}, refs=refs)
    assert refs == ["valid"]
    assert "amount" not in str(error.value)


@pytest.mark.parametrize("truth", [Decimal(1), Decimal(-1), Decimal("0.25")])
def test_true_precondition_requires_amount_and_returns_it_unchanged(truth):
    with pytest.raises(RegistryValidationError, match="no supplied value"):
        _evaluate({"valid": truth})
    assert _evaluate({"valid": truth, "amount": Decimal("19.75")}) == Decimal("19.75")


def test_missing_or_nonfinite_predicate_cannot_be_a_successful_zero():
    with pytest.raises(RegistryValidationError, match="no supplied value"):
        _evaluate({"amount": Decimal(0)})
    for value in (Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(RegistryValidationError, match="precondition"):
            _evaluate({"valid": value, "amount": Decimal(0)})


def test_boolean_precondition_and_json_hydration():
    expression = FormulaExpression.model_validate_json(_expression().model_dump_json())
    assert _evaluate({"amount": Decimal(0)}, booleans={"valid": True}, expression=expression) == 0
    with pytest.raises(RegistryValidationError, match="precondition"):
        _evaluate({}, booleans={"valid": False}, expression=expression)


@pytest.mark.parametrize("count", [0, 1, 3])
def test_precondition_arity_is_exactly_two(count):
    with pytest.raises((ValidationError, RegistryValidationError), match="expects 2 args"):
        FormulaExpression(op="require_condition", args=(FormulaExpression(literal=Decimal(1)),) * count)


@pytest.mark.parametrize("position", [0, 1])
def test_text_literal_is_not_admitted_as_predicate_or_amount(position):
    args = [FormulaExpression(literal=Decimal(1))] * 2
    args[position] = FormulaExpression(text_literal="1")
    with pytest.raises((ValidationError, RegistryValidationError), match="text_literal"):
        FormulaExpression(op="require_condition", args=tuple(args))
