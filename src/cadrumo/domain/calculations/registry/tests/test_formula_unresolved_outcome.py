"""A declared unresolved branch leaves one box without a value for a typed reason and never an amount."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..errors import RegistryValidationError
from ..formula_expression import evaluate_expression
from ..formula_runtime_ops import RegistryUnresolvedOutcomeReason, UnresolvedFormulaOutcomeError
from ..schema_formula import FormulaExpression
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon

_REASON = RegistryUnresolvedOutcomeReason.WAIVED_REFUND_RESULT_UNSUPPORTED


def _unresolved(reason: str) -> FormulaExpression:
    return FormulaExpression(op="unresolved_outcome", args=(FormulaExpression(text_literal=reason),))


def _branching(reason: str) -> FormulaExpression:
    return FormulaExpression(
        op="if_then_else",
        args=(FormulaExpression(binding="supported"), FormulaExpression(literal=Decimal(7)), _unresolved(reason)),
    )


def _evaluate(expression: FormulaExpression, *, supported: Decimal) -> Decimal:
    return evaluate_expression(
        expression,
        values={},
        binding_values={"supported": supported},
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
        filing_year=_YEAR,
    )


def test_the_branch_carries_its_typed_reason_and_the_other_branch_still_resolves() -> None:
    assert _evaluate(_branching(_REASON.value), supported=Decimal(1)) == Decimal(7)
    with pytest.raises(UnresolvedFormulaOutcomeError) as unresolved:
        _evaluate(_branching(_REASON.value), supported=Decimal(0))
    assert unresolved.value.reason is _REASON
    assert unresolved.value.context == {"filing_year": str(_YEAR)}


def test_a_reason_outside_the_closed_catalogue_is_refused_and_never_an_unresolved_outcome() -> None:
    with pytest.raises(RegistryValidationError, match="unknown reason"):
        _evaluate(_branching("not-a-reason"), supported=Decimal(0))


def test_the_hydrated_expression_keeps_the_reason() -> None:
    expression = FormulaExpression.model_validate_json(_branching(_REASON.value).model_dump_json())
    with pytest.raises(UnresolvedFormulaOutcomeError) as unresolved:
        _evaluate(expression, supported=Decimal(0))
    assert unresolved.value.reason is _REASON


@pytest.mark.parametrize("count", [0, 3])
def test_the_outcome_takes_a_reason_and_at_most_the_box_the_operator_states(count: int) -> None:
    with pytest.raises((ValidationError, RegistryValidationError), match=r"expects 1\.\.2 args"):
        FormulaExpression(op="unresolved_outcome", args=(FormulaExpression(text_literal=_REASON.value),) * count)


def test_a_second_operand_must_name_a_casilla_not_another_reason() -> None:
    with pytest.raises((ValidationError, RegistryValidationError), match="casilla leaf"):
        FormulaExpression(op="unresolved_outcome", args=(FormulaExpression(text_literal=_REASON.value),) * 2)


def test_the_reason_must_be_a_text_literal() -> None:
    with pytest.raises((ValidationError, RegistryValidationError), match="text_literal"):
        FormulaExpression(op="unresolved_outcome", args=(FormulaExpression(literal=Decimal(1)),))


def test_a_text_literal_is_still_refused_to_every_other_operator() -> None:
    with pytest.raises((ValidationError, RegistryValidationError), match="text_literal"):
        FormulaExpression(op="add", args=(FormulaExpression(text_literal=_REASON.value), FormulaExpression(literal=1)))
