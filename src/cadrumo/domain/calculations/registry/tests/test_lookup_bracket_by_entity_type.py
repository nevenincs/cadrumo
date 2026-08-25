"""Unit tests for the ``lookup_bracket_by_entity_type`` formula runtime op.

The op routes a bracket-table lookup through an entity-type-keyed
dispatch table, mirroring :mod:`test_lookup_bracket_by_ccaa` but
dispatching on the legal-form enum binding rather than the CCAA one.
It exists because the LIS Art. 29.1 micro-empresa rate is a
two-tranche scale (not a flat scalar), so the
``lookup_parameter_by_entity_type`` precedent — which rejects
``bracket_table`` parameters — cannot route a ``pyme`` profile.

These tests check graph wiring, validation errors and dispatch
mechanics. Hand-computed Decimal expectations are deliberately avoided
per ``.claude/rules/aeat-quality-gates.md``; the
oracle-grounded numeric assertions for the LIS Art. 29.1 scale live in
the Modelo 200 cuota-integra tests.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema_formula import BracketEntry, FormulaExpression, ParameterDefinition

from ..errors import RegistryValidationError
from ._formula_runtime_support import _evaluate

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _pyme_bracket_param() -> ParameterDefinition:
    """LIS Art. 29.1 micro-empresa two-tranche scale (2025 window).

    The numbers reproduce the registry-grounded
    ``is.modelo-200.tipo-gravamen-pyme`` parameter so the test exercises
    the same shape the dispatch-time wiring will resolve.
    """
    return ParameterDefinition.model_validate(
        {
            "id": "test-tipo-gravamen-pyme",
            "data_type": "bracket_table",
            "unit": "EUR",
            "bracket_axis": "filing_period",
            "legal_refs": ("ley-27-2014:art-29",),
            "source_refs": ("aeat-modelo-200-manual-2024",),
            "brackets": (
                BracketEntry(
                    lower_bound=Decimal("0"),
                    upper_bound=Decimal("50000"),
                    fixed_addition=Decimal("0"),
                    marginal_rate=Decimal("0.17"),
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
                BracketEntry(
                    lower_bound=Decimal("50000"),
                    upper_bound=None,
                    fixed_addition=Decimal("8500"),
                    marginal_rate=Decimal("0.20"),
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
        },
    )


def _alt_bracket_param() -> ParameterDefinition:
    """A distinct alternative bracket so dispatch is observably routing."""
    return ParameterDefinition.model_validate(
        {
            "id": "test-tipo-gravamen-alt",
            "data_type": "bracket_table",
            "unit": "EUR",
            "bracket_axis": "filing_period",
            "legal_refs": ("ley-27-2014:art-29",),
            "source_refs": ("aeat-modelo-200-manual-2024",),
            "brackets": (
                BracketEntry(
                    lower_bound=Decimal("0"),
                    upper_bound=None,
                    fixed_addition=Decimal("0"),
                    marginal_rate=Decimal("0.25"),
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
        },
    )


def _dispatch_expression(base: Decimal) -> FormulaExpression:
    return FormulaExpression.model_validate(
        {
            "op": "lookup_bracket_by_entity_type",
            "args": (
                {"literal": base},
                {"binding": "test-legal-entity-form"},
                {
                    "dispatch_table": {
                        "pyme": "test-tipo-gravamen-pyme",
                        "other": "test-tipo-gravamen-alt",
                    },
                },
            ),
        },
    )


def test_lookup_bracket_by_entity_type_dispatches_to_the_keyed_parameter() -> None:
    """Flipping the legal-entity-form binding selects a different bracket table.

    Asserts dispatch mechanics: two distinct bracket tables produce two
    distinct results for the same base. The pyme scale charges 17% on
    the first 50.000 EUR tranche and 20% above; the alt scale charges a
    flat 25%. Asserting they differ on the same base verifies the
    dispatch picks the routed parameter.
    """
    base = Decimal("100000")
    parameters = {p.id: p for p in (_pyme_bracket_param(), _alt_bracket_param())}

    pyme_result = _evaluate(
        _dispatch_expression(base),
        parameters=parameters,
        enum_bindings={"test-legal-entity-form": "pyme"},
    )
    alt_result = _evaluate(
        _dispatch_expression(base),
        parameters=parameters,
        enum_bindings={"test-legal-entity-form": "other"},
    )

    assert pyme_result != alt_result
    # pyme bracket caps the first 50.000 at 17%, so its cuota on 100.000
    # must be strictly less than the alt flat-25% cuota.
    assert pyme_result < alt_result


def test_lookup_bracket_by_entity_type_rejects_a_scalar_parameter() -> None:
    """Dispatching to a non-bracket_table parameter is a validation error.

    The whole reason this op exists alongside
    ``lookup_parameter_by_entity_type`` is that the micro-empresa rate
    is a tranche scale, not a flat scalar. Symmetrically, this op must
    reject a scalar parameter — the wrong-shape mistake must fail
    loudly rather than silently producing a zero-base scalar lookup.
    """
    expression = FormulaExpression.model_validate(
        {
            "op": "lookup_bracket_by_entity_type",
            "args": (
                {"literal": Decimal("100000")},
                {"binding": "test-legal-entity-form"},
                {"dispatch_table": {"sl": "test-scalar-rate"}},
            ),
        },
    )
    parameters = {
        "test-scalar-rate": ParameterDefinition.model_validate(
            {
                "id": "test-scalar-rate",
                "data_type": "ratio",
                "unit": "percent",
                "legal_refs": ("ley-27-2014:art-29",),
                "source_refs": ("aeat-modelo-200-manual-2024",),
                "values": (
                    {
                        "value": Decimal("25"),
                        "date_axis": "filing_period",
                        "valid_from": date(2025, 1, 1),
                    },
                ),
            },
        ),
    }
    with pytest.raises(RegistryValidationError, match="must declare data_type='bracket_table'"):
        _evaluate(expression, parameters=parameters, enum_bindings={"test-legal-entity-form": "sl"})


def test_lookup_bracket_by_entity_type_raises_on_missing_dispatch_key() -> None:
    """An enum value outside the dispatch table fails loudly, no default."""
    expression = _dispatch_expression(Decimal("100000"))
    parameters = {p.id: p for p in (_pyme_bracket_param(), _alt_bracket_param())}

    with pytest.raises(RegistryValidationError, match="missing key 'unknown'"):
        _evaluate(
            expression,
            parameters=parameters,
            enum_bindings={"test-legal-entity-form": "unknown"},
        )


def test_lookup_bracket_by_entity_type_raises_when_enum_binding_is_unset() -> None:
    """If the legal-entity-form binding has no value supplied, the op raises."""
    expression = _dispatch_expression(Decimal("100000"))
    parameters = {p.id: p for p in (_pyme_bracket_param(), _alt_bracket_param())}

    with pytest.raises(RegistryValidationError, match="has no supplied value"):
        _evaluate(expression, parameters=parameters, enum_bindings={})


def test_lookup_bracket_by_entity_type_requires_three_args() -> None:
    """The op must declare exactly base / binding / dispatch_table.

    FormulaExpression.model_validate() now enforces op arity centrally
    (require_formula_operator_arity, at construction), so a 2-arg expression
    can no longer reach _evaluate's own arity check via normal validation.
    model_construct() bypasses that model-level validator to exercise this
    op's defense-in-depth check directly.
    """
    expression = FormulaExpression.model_construct(
        op="lookup_bracket_by_entity_type",
        args=(
            FormulaExpression.model_validate({"literal": Decimal("100000")}),
            FormulaExpression.model_validate({"binding": "test-legal-entity-form"}),
        ),
    )
    with pytest.raises(RegistryValidationError, match="expects 3 args"):
        _evaluate(
            expression,
            parameters={},
            enum_bindings={"test-legal-entity-form": "pyme"},
        )


def test_lookup_bracket_by_entity_type_requires_binding_at_args_1() -> None:
    """The args[1] leaf must be a binding, not a literal or casilla."""
    expression = FormulaExpression.model_validate(
        {
            "op": "lookup_bracket_by_entity_type",
            "args": (
                {"literal": Decimal("100000")},
                {"literal": Decimal("0")},
                {"dispatch_table": {"pyme": "test-tipo-gravamen-pyme"}},
            ),
        },
    )
    with pytest.raises(RegistryValidationError, match="requires args\\[1\\] to be a binding"):
        _evaluate(
            expression,
            parameters={p.id: p for p in (_pyme_bracket_param(),)},
            enum_bindings={},
        )


def test_lookup_bracket_by_entity_type_requires_dispatch_table_at_args_2() -> None:
    """The args[2] leaf must be a dispatch_table, not a literal."""
    expression = FormulaExpression.model_validate(
        {
            "op": "lookup_bracket_by_entity_type",
            "args": (
                {"literal": Decimal("100000")},
                {"binding": "test-legal-entity-form"},
                {"literal": Decimal("0")},
            ),
        },
    )
    with pytest.raises(RegistryValidationError, match="requires args\\[2\\] to be a dispatch_table"):
        _evaluate(
            expression,
            parameters={},
            enum_bindings={"test-legal-entity-form": "pyme"},
        )
