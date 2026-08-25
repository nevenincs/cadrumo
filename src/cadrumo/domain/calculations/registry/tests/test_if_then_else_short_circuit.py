"""Contract test guarding the `if_then_else` short-circuit semantics.

The runtime previously evaluated both branches of an `if_then_else`
eagerly (list comprehension at the args build site), so an
error-producing expression in the false branch would surface even
when the predicate routed around it. The fix evaluates the predicate
first and then only the selected branch.

This matters in production for guarded division (modelo 303 prorrata
falls back to 0 when ``volumen_total = 0``). Without short-circuit
the divide-by-zero raised even for the zero-denominator path the
predicate explicitly guarded against.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..schema import FormulaExpression
from ._formula_runtime_support import _evaluate

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_if_then_else_evaluates_only_the_true_branch_when_predicate_truthy() -> None:
    """False branch must not be evaluated when predicate is non-zero.

    The false branch here is a divide-by-zero. If the runtime evaluated
    both branches eagerly the test would raise. The selected (true)
    branch returns the literal 99.
    """

    expression = FormulaExpression(
        op="if_then_else",
        args=(
            FormulaExpression(literal=Decimal("1")),  # truthy predicate
            FormulaExpression(literal=Decimal("99")),  # selected branch
            FormulaExpression(  # false branch — divide-by-zero
                op="divide",
                args=(
                    FormulaExpression(literal=Decimal("1")),
                    FormulaExpression(literal=Decimal("0")),
                ),
            ),
        ),
    )

    assert _evaluate(expression, {}) == Decimal("99")


def test_if_then_else_evaluates_only_the_false_branch_when_predicate_falsy() -> None:
    """True branch must not be evaluated when predicate is zero.

    Symmetric guard: the true branch divides by zero; the predicate
    is zero so only the false branch (returning -7) is evaluated.
    """

    expression = FormulaExpression(
        op="if_then_else",
        args=(
            FormulaExpression(literal=Decimal("0")),  # falsy predicate
            FormulaExpression(  # true branch — divide-by-zero
                op="divide",
                args=(
                    FormulaExpression(literal=Decimal("1")),
                    FormulaExpression(literal=Decimal("0")),
                ),
            ),
            FormulaExpression(literal=Decimal("-7")),  # selected branch
        ),
    )

    assert _evaluate(expression, {}) == Decimal("-7")


def test_if_then_else_predicate_evaluation_resolves_nested_op() -> None:
    """The predicate itself can be a nested op; that op IS evaluated."""

    expression = FormulaExpression(
        op="if_then_else",
        args=(
            FormulaExpression(  # nested op as predicate: 5 > 3 → 1
                op="greater_than",
                args=(
                    FormulaExpression(literal=Decimal("5")),
                    FormulaExpression(literal=Decimal("3")),
                ),
            ),
            FormulaExpression(literal=Decimal("42")),
            FormulaExpression(literal=Decimal("-1")),
        ),
    )

    assert _evaluate(expression, {}) == Decimal("42")
