"""Text selectors do not inherit spreadsheet coercion or numeric defaults."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..errors import RegistryValidationError
from ..formula_runtime import evaluate_expression
from ..formula_runtime_ops import UnresolvedFormulaDependencyError
from ..schema_formula import FormulaExpression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _expression():
    return FormulaExpression(
        op="text_equal", args=(FormulaExpression(binding="country"), FormulaExpression(casilla_id="destination"))
    )


def _evaluate(
    country,
    destination,
    *,
    binding_values=None,
    unresolved_binding_ids=frozenset(),
    text_casilla_ids=frozenset({"destination"}),
    operand_refs=None,
    operand_casilla_refs=None,
    operand_values=None,
    expression=None,
):
    return evaluate_expression(
        expression if expression is not None else _expression(),
        values={},
        binding_values=binding_values or {},
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=operand_refs if operand_refs is not None else [],
        operand_casilla_refs=operand_casilla_refs if operand_casilla_refs is not None else [],
        operand_values=operand_values if operand_values is not None else [],
        enum_binding_values={"country": country},
        text_values={"destination": destination},
        text_casilla_ids=text_casilla_ids,
        unresolved_binding_ids=unresolved_binding_ids,
    )


@pytest.mark.parametrize(
    "left,right,expected", [("DE", "DE", 1), ("DE", "FR", 0), ("de", "DE", 0), ("01", "1", 0), ("DE ", "DE", 0)]
)
def test_comparison_is_exact(left, right, expected):
    assert _evaluate(left, right) == Decimal(expected)


@pytest.mark.parametrize("left,right", [("", "DE"), ("DE", ""), (None, "DE"), (1, "1")])
def test_missing_or_nontext_values_never_become_a_false_match(left, right):
    with pytest.raises(RegistryValidationError):
        _evaluate(left, right)


def test_ambiguous_channels_and_unresolved_operands_are_refused():
    with pytest.raises(RegistryValidationError, match="ambiguous"):
        _evaluate("DE", "DE", binding_values={"country": Decimal(1)})
    with pytest.raises(UnresolvedFormulaDependencyError):
        _evaluate("DE", "DE", unresolved_binding_ids=frozenset({"country"}))
    with pytest.raises(RegistryValidationError, match="text casilla"):
        _evaluate("DE", "DE", text_casilla_ids=frozenset())


def test_provenance_records_both_owners_without_coercing_their_text():
    refs, casillas, values = [], [], []
    assert _evaluate("DE", "DE", operand_refs=refs, operand_casilla_refs=casillas, operand_values=values) == 1
    assert refs == ["country"]
    assert casillas == ["destination"]
    assert values == [Decimal(1)]


def test_numeric_literals_cannot_masquerade_as_text_operands():
    with pytest.raises((RegistryValidationError, ValidationError)):
        FormulaExpression(
            op="text_equal", args=(FormulaExpression(literal=Decimal(1)), FormulaExpression(binding="country"))
        )


def test_country_selection_reads_only_the_matching_amount():
    expression = FormulaExpression(
        op="if_then_else",
        args=(_expression(), FormulaExpression(binding="amount"), FormulaExpression(literal=Decimal(0))),
    )
    assert _evaluate("FR", "DE", expression=expression) == 0
    assert _evaluate("DE", "DE", expression=expression, binding_values={"amount": Decimal("190")}) == 190
    with pytest.raises(RegistryValidationError):
        _evaluate("DE", "DE", expression=expression)


@pytest.mark.parametrize("literal", ["DE", 'a"b,c', "=1+1", "01"])
def test_literal_comparison_hydrates_and_has_no_fictitious_binding_provenance(literal):
    expression = FormulaExpression(
        op="text_equal", args=(FormulaExpression(binding="country"), FormulaExpression(text_literal=literal))
    )
    expression = FormulaExpression.model_validate_json(expression.model_dump_json())
    refs, casillas, values = [], [], []
    assert (
        _evaluate(
            literal,
            None,
            expression=expression,
            operand_refs=refs,
            operand_casilla_refs=casillas,
            operand_values=values,
        )
        == 1
    )
    assert refs == ["country"]
    assert casillas == []
    assert values == [Decimal(1)]
    assert _evaluate(literal + " ", None, expression=expression) == 0


def test_literal_to_text_casilla_and_literal_to_literal_are_exact():
    expression = FormulaExpression(
        op="text_equal", args=(FormulaExpression(text_literal="DE"), FormulaExpression(casilla_id="destination"))
    )
    assert _evaluate(None, "DE", expression=expression) == 1
    assert _evaluate(None, "de", expression=expression) == 0
    both = FormulaExpression(
        op="text_equal", args=(FormulaExpression(text_literal="01"), FormulaExpression(text_literal="1"))
    )
    assert _evaluate(None, None, expression=both) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"text_literal": ""},
        {"text_literal": "x" * 257},
        {"text_literal": 1},
        {"text_literal": "DE", "binding": "country"},
        {"text_literal": "DE", "literal": "1"},
        {"text_literal": "DE", "casilla_id": "destination"},
        {"text_literal": "DE", "op": "sum", "args": [{"literal": "1"}]},
    ],
)
def test_text_literal_shape_is_closed_and_bounded(payload):
    with pytest.raises((ValidationError, RegistryValidationError)):
        FormulaExpression.model_validate(payload)


@pytest.mark.parametrize("op", ["add", "multiply", "equal"])
def test_text_literal_cannot_be_used_by_numeric_operators(op):
    with pytest.raises((ValidationError, RegistryValidationError), match="text_literal"):
        FormulaExpression(op=op, args=(FormulaExpression(text_literal="1"), FormulaExpression(literal=Decimal(1))))


def test_numeric_runtime_rejects_standalone_and_bypassed_numeric_text_leaf():
    text = FormulaExpression(text_literal="1")
    with pytest.raises(RegistryValidationError, match="text_literal"):
        _evaluate(None, None, expression=text)
    numeric = FormulaExpression(op="add", args=(FormulaExpression(literal=Decimal(1)),) * 2)
    bypassed = numeric.model_copy(update={"args": (text, FormulaExpression(literal=Decimal(1)))})
    with pytest.raises(RegistryValidationError, match="text_literal"):
        _evaluate(None, None, expression=bypassed)
    assert _evaluate(None, None, expression=numeric) == 2
