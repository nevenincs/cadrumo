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
from graphlib import CycleError

import pytest

from .....core import CasillaId, validated_casilla_id
from .....tests.registry_tree import bundled_registry_tree
from .._validate_formulas import validate_formula_dag
from ..runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_casilla_refs,
    expression_parameter_refs,
    expression_relation_refs,
    formula_evaluation_order,
)
from ..schema import ModeloRevision
from ..schema_formula import FormulaExpression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASILLA_0001: CasillaId = validated_casilla_id("0001", surface="_CASILLA_0001")
_CASILLA_0002: CasillaId = validated_casilla_id("0002", surface="_CASILLA_0002")
_CASILLA_0003: CasillaId = validated_casilla_id("0003", surface="_CASILLA_0003")
_CASILLA_0505: CasillaId = validated_casilla_id("0505", surface="_CASILLA_0505")
_M210_RATE_FORMULA_ID = "m210-tipo-gravamen-2025-resolve"
_M210_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"


def _leaf(**kwargs: object) -> FormulaExpression:
    """Build a leaf FormulaExpression by validating a single-key payload."""

    return FormulaExpression.model_validate(kwargs)


def _operator(op: str, *args: FormulaExpression) -> FormulaExpression:
    """Build a non-leaf FormulaExpression by validating its op + args."""

    return FormulaExpression.model_validate({"op": op, "args": args})


def _m210_2025_revision() -> ModeloRevision:
    # Compile-only load (no full-registry validation) so the M210 formula-graph
    # shape assertions are independent of unrelated peer modelo churn.
    modelos, _catalogues = bundled_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == "210").revisions["2025"]


def _m130_2025_revision() -> ModeloRevision:
    modelos, _catalogues = bundled_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == "130").revisions["2019-y-siguientes"]


def test_expression_casilla_refs_returns_direct_leaf() -> None:
    assert expression_casilla_refs(_leaf(casilla_id=_CASILLA_0001)) == (_CASILLA_0001,)


def test_expression_casilla_refs_walks_nested_args_in_order() -> None:
    expression = _operator(
        "add",
        _leaf(casilla_id=_CASILLA_0001),
        _operator("subtract", _leaf(casilla_id=_CASILLA_0002), _leaf(casilla_id=_CASILLA_0003)),
    )

    assert expression_casilla_refs(expression) == (_CASILLA_0001, _CASILLA_0002, _CASILLA_0003)


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
        _leaf(casilla_id=_CASILLA_0505),
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
            _leaf(casilla_id=_CASILLA_0505),
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


def test_formula_evaluation_order_preserves_the_committed_modelo_130_settlement_chain() -> None:
    """The official M130 settlement chain must evaluate inputs before its final result."""

    order = formula_evaluation_order(_m130_2025_revision())

    assert order.index("03") < order.index("04") < order.index("07") < order.index("12")
    assert order.index("12") < order.index("14") < order.index("17") < order.index("19")


def test_formula_dag_validation_refuses_a_cycle_through_the_canonical_order_builder() -> None:
    """A cycle injected into the real M130 settlement chain has no valid evaluation order."""

    revision = _m130_2025_revision()
    formulas = tuple(
        formula.model_copy(update={"expression": FormulaExpression(casilla_id="19")})
        if formula.target_casilla_id == "03"
        else formula
        for formula in revision.formulas
    )
    cyclic_revision = revision.model_copy(update={"formulas": formulas})

    with pytest.raises(CycleError):
        formula_evaluation_order(cyclic_revision)

    failures = validate_formula_dag("modelo 130", cyclic_revision)

    assert len(failures) == 1
    assert failures[0].startswith("modelo 130: formula graph cycle:")


def test_enum_consumed_binding_ids_reads_current_irnr_resolve_tipo_gravamen_country_arg() -> None:
    """The committed M210 2025 five-arg rate formula routes country as an enum binding."""

    revision = _m210_2025_revision()
    formula = next(formula for formula in revision.formulas if formula.id == _M210_RATE_FORMULA_ID)
    expression = formula.expression
    assert expression.op == "irnr_resolve_tipo_gravamen"
    assert len(expression.args) == 5
    assert expression.args[2].parameter == "m210-tipo-gravamen-2025"
    assert expression.args[4].binding == _M210_COUNTRY_BINDING

    enum_ids = enum_consumed_binding_ids(revision)

    assert _M210_COUNTRY_BINDING in enum_ids
    assert "m210-tipo-gravamen-2025" not in enum_ids


def test_enum_consumed_binding_ids_ignores_retired_irnr_six_arg_country_arg() -> None:
    """The retired six-arg (convenio-parameter) rate formula is not a current enum-dispatch shape."""

    revision = _m210_2025_revision()
    formula = next(formula for formula in revision.formulas if formula.id == _M210_RATE_FORMULA_ID)
    # FormulaExpression.model_validate() now enforces op arity centrally
    # (require_formula_operator_arity, at construction), so this retired
    # 6-arg shape can no longer be built via normal validation.
    # model_construct() bypasses that model-level validator so the retired
    # shape can still be exercised here.
    retired_expression = FormulaExpression.model_construct(
        op="irnr_resolve_tipo_gravamen",
        args=(
            FormulaExpression.model_validate({"casilla_id": "tipo_renta"}),
            FormulaExpression.model_validate({"casilla_id": "base_imponible"}),
            FormulaExpression.model_validate({"parameter": "m210-tipo-gravamen-2025"}),
            FormulaExpression.model_validate({"parameter": "m210-convenio-rates"}),
            FormulaExpression.model_validate({"parameter": "m210-pension-tarifa-2025"}),
            FormulaExpression.model_validate({"binding": _M210_COUNTRY_BINDING}),
        ),
    )
    retired_formula = formula.model_copy(update={"expression": retired_expression})
    retired_revision = revision.model_copy(update={"formulas": (retired_formula,)})

    assert enum_consumed_binding_ids(retired_revision) == frozenset()


def test_walkers_return_empty_for_unrelated_leaf_kinds() -> None:
    """A literal-only leaf yields no refs across every helper."""
    literal_leaf = _leaf(literal=Decimal("100"))

    assert expression_casilla_refs(literal_leaf) == ()
    assert expression_binding_refs(literal_leaf) == ()
    assert expression_parameter_refs(literal_leaf) == ()
    assert expression_relation_refs(literal_leaf) == ()
