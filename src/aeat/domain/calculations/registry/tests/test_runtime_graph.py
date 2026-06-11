"""Focused unit tests for the public _runtime_graph helpers.

These walkers underpin the validator orphan-detection passes, the
RegistryQueryService input_* surfaces, the drift-detection sweep, and
the formula evaluation order. Indirect coverage exists through the
registry-load tests, but a regression in a helper would only surface
as a registry-load failure of the committed Modelo 100 corpus, which
is slow signal. These tests pin the helpers' graph-walking contracts
at the unit level so refactors fail fast.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._runtime_graph import (
    expression_binding_refs,
    expression_casilla_refs,
    expression_parameter_refs,
    expression_relation_refs,
)
from .._schema import FormulaExpression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _leaf(**kwargs: object) -> FormulaExpression:
    """Build a leaf FormulaExpression by validating a single-key payload."""

    return FormulaExpression.model_validate(kwargs)


def _operator(op: str, *args: FormulaExpression) -> FormulaExpression:
    """Build a non-leaf FormulaExpression by validating its op + args."""

    return FormulaExpression.model_validate({"op": op, "args": args})


def test_expression_casilla_refs_returns_direct_leaf() -> None:
    assert expression_casilla_refs(_leaf(casilla="0001")) == ("0001",)


def test_expression_casilla_refs_walks_nested_args_in_order() -> None:
    expression = _operator(
        "add",
        _leaf(casilla="0001"),
        _operator("subtract", _leaf(casilla="0002"), _leaf(casilla="0003")),
    )

    assert expression_casilla_refs(expression) == ("0001", "0002", "0003")


def test_expression_binding_refs_walks_nested_args() -> None:
    expression = _operator(
        "add",
        _leaf(binding="renta-2025-ledger-expense-0186-deductible"),
        _operator("subtract", _leaf(binding="renta-2025-ledger-expense-0192-deductible"), _leaf(literal=Decimal("0"))),
    )

    assert expression_binding_refs(expression) == (
        "renta-2025-ledger-expense-0186-deductible",
        "renta-2025-ledger-expense-0192-deductible",
    )


def test_expression_parameter_refs_returns_direct_leaf() -> None:
    assert expression_parameter_refs(_leaf(parameter="renta-2025-escala-estatal-base-general")) == (
        "renta-2025-escala-estatal-base-general",
    )


def test_expression_parameter_refs_walks_dispatch_table_values() -> None:
    """Regression coverage for commit 1adf3d0b: dispatch_table values point at
    parameter ids exactly like the direct ``parameter`` leaf, so the walker
    must enumerate them. A pre-fix walker that visited only the direct
    ``expression.parameter`` would undercount references for every
    lookup_bracket_by_ccaa formula.
    """
    expression = _operator(
        "lookup_bracket_by_ccaa",
        _leaf(casilla="0505"),
        _leaf(binding="renta-2025-profile-tax-residence-ccaa"),
        _leaf(
            dispatch_table={
                "madrid": "renta-2025-escala-autonomica-madrid-base-general",
                "cataluna": "renta-2025-escala-autonomica-cataluna-base-general",
            },
        ),
    )

    refs = expression_parameter_refs(expression)

    assert set(refs) == {
        "renta-2025-escala-autonomica-madrid-base-general",
        "renta-2025-escala-autonomica-cataluna-base-general",
    }


def test_expression_parameter_refs_walks_dispatch_table_inside_nested_args() -> None:
    """dispatch_table leaves nested inside an outer operator are still walked."""
    expression = _operator(
        "add",
        _leaf(parameter="renta-2025-deduccion-rate"),
        _operator(
            "lookup_bracket_by_ccaa",
            _leaf(casilla="0505"),
            _leaf(binding="renta-2025-profile-tax-residence-ccaa"),
            _leaf(dispatch_table={"madrid": "renta-2025-escala-autonomica-madrid-base-general"}),
        ),
    )

    refs = expression_parameter_refs(expression)

    assert set(refs) == {
        "renta-2025-deduccion-rate",
        "renta-2025-escala-autonomica-madrid-base-general",
    }


def test_expression_relation_refs_walks_nested_args() -> None:
    expression = _operator(
        "add",
        _leaf(relation="modelo-130-rel-base-1t"),
        _leaf(relation="modelo-130-rel-base-2t"),
    )

    assert expression_relation_refs(expression) == (
        "modelo-130-rel-base-1t",
        "modelo-130-rel-base-2t",
    )


def test_walkers_return_empty_for_unrelated_leaf_kinds() -> None:
    """A literal-only leaf yields no refs across every helper."""
    literal_leaf = _leaf(literal=Decimal("100"))

    assert expression_casilla_refs(literal_leaf) == ()
    assert expression_binding_refs(literal_leaf) == ()
    assert expression_parameter_refs(literal_leaf) == ()
    assert expression_relation_refs(literal_leaf) == ()
