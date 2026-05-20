"""Unit tests for the ``lookup_bracket_by_ccaa`` formula runtime op.

The op routes a bracket-table lookup through a CCAA-keyed dispatch
table: arg[0] is the base value, arg[1] is the binding leaf carrying
the operator's CCAA enum value, and arg[2] is a ``dispatch_table``
leaf mapping CCAA strings to bracket-table parameter ids. The op
delegates to ``_resolve_bracket`` against the resolved parameter.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ._errors import RegistryValidationError
from ._formula_runtime import _evaluate_expression
from ._schema import BracketEntry, FormulaExpression, ParameterDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _madrid_bracket_param() -> ParameterDefinition:
    """Return a synthetic Madrid 2025 autonomic bracket parameter for tests."""
    return ParameterDefinition.model_validate(
        {
            "id": "renta-2025-escala-autonomica-madrid-base-general",
            "data_type": "bracket_table",
            "unit": "EUR",
            "bracket_axis": "filing_period",
            "legal_refs": ("ley-35-2006:art-74",),
            "source_refs": ("lirpf-cuota-chain-authority",),
            "brackets": (
                BracketEntry(
                    lower_bound=Decimal("0"),
                    upper_bound=Decimal("12450"),
                    fixed_addition=Decimal("0"),
                    marginal_rate=Decimal("0.085"),
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
                BracketEntry(
                    lower_bound=Decimal("12450"),
                    upper_bound=None,
                    fixed_addition=Decimal("1058.25"),
                    marginal_rate=Decimal("0.103"),
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
        }
    )


def _cataluna_bracket_param() -> ParameterDefinition:
    """Return a distinct synthetic Cataluña parameter so dispatch is observable."""
    return ParameterDefinition.model_validate(
        {
            "id": "renta-2025-escala-autonomica-cataluna-base-general",
            "data_type": "bracket_table",
            "unit": "EUR",
            "bracket_axis": "filing_period",
            "legal_refs": ("ley-35-2006:art-74",),
            "source_refs": ("lirpf-cuota-chain-authority",),
            "brackets": (
                BracketEntry(
                    lower_bound=Decimal("0"),
                    upper_bound=Decimal("12450"),
                    fixed_addition=Decimal("0"),
                    marginal_rate=Decimal("0.105"),
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
                BracketEntry(
                    lower_bound=Decimal("12450"),
                    upper_bound=None,
                    fixed_addition=Decimal("1307.25"),
                    marginal_rate=Decimal("0.12"),
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
        }
    )


def _dispatch_expression(base: Decimal) -> FormulaExpression:
    """Build a lookup_bracket_by_ccaa expression dispatching Madrid + Cataluña."""
    return FormulaExpression.model_validate(
        {
            "op": "lookup_bracket_by_ccaa",
            "args": (
                {"literal": base},
                {"binding": "renta-2025-profile-tax-residence-ccaa"},
                {
                    "dispatch_table": {
                        "madrid": "renta-2025-escala-autonomica-madrid-base-general",
                        "cataluna": "renta-2025-escala-autonomica-cataluna-base-general",
                    }
                },
            ),
        }
    )


def _evaluate(
    expression: FormulaExpression,
    *,
    parameters: dict[str, ParameterDefinition],
    enum_bindings: dict[str, str],
) -> Decimal:
    operand_refs: list[str] = []
    operand_values: list[Decimal] = []
    return _evaluate_expression(
        expression,
        values={},
        binding_values={},
        parameters=parameters,
        date_context={"filing_period": date(2025, 12, 31)},
        relation_values={},
        operand_refs=operand_refs,
        operand_values=operand_values,
        enum_binding_values=enum_bindings,
    )


def test_lookup_bracket_by_ccaa_dispatches_to_madrid_when_residence_is_madrid() -> None:
    """A Madrid-resident profile routes the lookup against the Madrid scale."""
    base = Decimal("20000")
    expression = _dispatch_expression(base)
    parameters = {
        "renta-2025-escala-autonomica-madrid-base-general": _madrid_bracket_param(),
        "renta-2025-escala-autonomica-cataluna-base-general": _cataluna_bracket_param(),
    }
    enum_bindings = {"renta-2025-profile-tax-residence-ccaa": "madrid"}

    result = _evaluate(expression, parameters=parameters, enum_bindings=enum_bindings)

    # Madrid: 1058.25 + (20000-12450) * 0.103 = 1058.25 + 7550 * 0.103 = 1058.25 + 777.65 = 1835.90
    assert result == Decimal("1835.90")


def test_lookup_bracket_by_ccaa_dispatches_to_cataluna_when_residence_is_cataluna() -> None:
    """The same expression routes to Cataluña's scale when the binding flips."""
    base = Decimal("20000")
    expression = _dispatch_expression(base)
    parameters = {
        "renta-2025-escala-autonomica-madrid-base-general": _madrid_bracket_param(),
        "renta-2025-escala-autonomica-cataluna-base-general": _cataluna_bracket_param(),
    }
    enum_bindings = {"renta-2025-profile-tax-residence-ccaa": "cataluna"}

    result = _evaluate(expression, parameters=parameters, enum_bindings=enum_bindings)

    # Cataluña: 1307.25 + (20000-12450) * 0.12 = 1307.25 + 906 = 2213.25
    assert result == Decimal("2213.25")


def test_lookup_bracket_by_ccaa_dispatches_with_entry_array_table() -> None:
    """The reviewable dispatch_table_entries authoring shape behaves identically."""
    expression = FormulaExpression.model_validate(
        {
            "op": "lookup_bracket_by_ccaa",
            "args": (
                {"literal": Decimal("20000")},
                {"binding": "renta-2025-profile-tax-residence-ccaa"},
                {
                    "dispatch_table_entries": [
                        {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                        {"key": "cataluna", "parameter": "renta-2025-escala-autonomica-cataluna-base-general"},
                    ]
                },
            ),
        }
    )
    parameters = {
        "renta-2025-escala-autonomica-madrid-base-general": _madrid_bracket_param(),
        "renta-2025-escala-autonomica-cataluna-base-general": _cataluna_bracket_param(),
    }

    result = _evaluate(
        expression,
        parameters=parameters,
        enum_bindings={"renta-2025-profile-tax-residence-ccaa": "madrid"},
    )

    assert result == Decimal("1835.90")


def test_lookup_bracket_by_ccaa_raises_on_missing_dispatch_key() -> None:
    """A CCAA value not in the dispatch_table raises RegistryValidationError."""
    expression = _dispatch_expression(Decimal("20000"))
    parameters = {
        "renta-2025-escala-autonomica-madrid-base-general": _madrid_bracket_param(),
        "renta-2025-escala-autonomica-cataluna-base-general": _cataluna_bracket_param(),
    }
    enum_bindings = {"renta-2025-profile-tax-residence-ccaa": "andalucia"}

    with pytest.raises(RegistryValidationError, match="missing CCAA 'andalucia'"):
        _evaluate(expression, parameters=parameters, enum_bindings=enum_bindings)


def test_lookup_bracket_by_ccaa_raises_when_dispatched_parameter_is_not_bracket_table() -> None:
    """A dispatch_table that resolves to a non-bracket_table parameter is rejected."""
    expression = FormulaExpression.model_validate(
        {
            "op": "lookup_bracket_by_ccaa",
            "args": (
                {"literal": Decimal("20000")},
                {"binding": "renta-2025-profile-tax-residence-ccaa"},
                {"dispatch_table": {"madrid": "renta-2025-some-rate-parameter"}},
            ),
        }
    )
    parameters = {
        "renta-2025-some-rate-parameter": ParameterDefinition.model_validate(
            {
                "id": "renta-2025-some-rate-parameter",
                "data_type": "ratio",
                "unit": "ratio",
                "values": (
                    {
                        "value": Decimal("0.21"),
                        "date_axis": "filing_period",
                        "valid_from": date(2025, 1, 1),
                    },
                ),
                "legal_refs": ("ley-35-2006:art-74",),
                "source_refs": ("lirpf-cuota-chain-authority",),
            }
        ),
    }
    enum_bindings = {"renta-2025-profile-tax-residence-ccaa": "madrid"}

    with pytest.raises(RegistryValidationError, match="must declare data_type='bracket_table'"):
        _evaluate(expression, parameters=parameters, enum_bindings=enum_bindings)


def test_lookup_bracket_by_ccaa_raises_when_enum_binding_is_unset() -> None:
    """If the CCAA binding has no value supplied, the op raises."""
    expression = _dispatch_expression(Decimal("20000"))
    parameters = {
        "renta-2025-escala-autonomica-madrid-base-general": _madrid_bracket_param(),
        "renta-2025-escala-autonomica-cataluna-base-general": _cataluna_bracket_param(),
    }
    enum_bindings: dict[str, str] = {}

    with pytest.raises(RegistryValidationError, match="has no supplied value"):
        _evaluate(expression, parameters=parameters, enum_bindings=enum_bindings)
