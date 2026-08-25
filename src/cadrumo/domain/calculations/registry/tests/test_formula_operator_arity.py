"""Schema and runtime share one registry formula-operator arity authority."""

from __future__ import annotations

from decimal import Decimal
from typing import get_args

import pytest
from pydantic import ValidationError

from ..errors import RegistryValidationError
from .._formula_operator_contracts import FORMULA_OPERATOR_ARITIES
from ..formula_runtime_ops import evaluate_args_op
from ..schema import FormulaExpression
from ..schema_base import FormulaOperator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _literal(value: str = "1") -> FormulaExpression:
    return FormulaExpression(literal=Decimal(value))


def test_every_formula_operator_has_one_canonical_arity_contract() -> None:
    """The closed schema vocabulary and shared metadata cannot drift."""
    assert set(FORMULA_OPERATOR_ARITIES) == set(get_args(FormulaOperator))


@pytest.mark.parametrize(
    ("op", "arg_count", "expected"),
    [
        pytest.param("subtract", 1, "expects 2 args, got 1", id="binary-too-few"),
        pytest.param("negate", 2, "expects 1 arg, got 2", id="unary-too-many"),
        pytest.param("if_then_else", 2, "expects 3 args, got 2", id="special-too-few"),
        pytest.param("m210_resolve_base_imponible", 11, "expects 12 args, got 11", id="domain-op-too-few"),
        pytest.param("sum", 0, "expects at least 1 arg, got 0", id="variadic-empty"),
    ],
)
def test_formula_schema_refuses_runtime_invalid_operator_arity(
    op: FormulaOperator,
    arg_count: int,
    expected: str,
) -> None:
    with pytest.raises(ValidationError, match=expected):
        FormulaExpression(op=op, args=tuple(_literal() for _ in range(arg_count)))


@pytest.mark.parametrize(
    ("op", "arg_count"),
    [
        pytest.param("copy", 1, id="unary"),
        pytest.param("subtract", 2, id="binary"),
        pytest.param("clamp", 3, id="ternary"),
        pytest.param("add", 13, id="variadic"),
        pytest.param("m100_resolve_renta_inmobiliaria_imputada", 9, id="domain-op"),
    ],
)
def test_formula_schema_accepts_runtime_valid_operator_arity(op: FormulaOperator, arg_count: int) -> None:
    expression = FormulaExpression(op=op, args=tuple(_literal() for _ in range(arg_count)))

    assert len(expression.args) == arg_count


def test_generic_runtime_dispatch_uses_the_same_arity_contract() -> None:
    with pytest.raises(RegistryValidationError, match="formula op 'multiply' expects at least 1 arg, got 0"):
        evaluate_args_op("multiply", [])


def test_generic_runtime_dispatch_still_calculates_a_valid_operator() -> None:
    assert evaluate_args_op("subtract", [Decimal("7"), Decimal("2")]) == Decimal("5")
