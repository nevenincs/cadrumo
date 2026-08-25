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

from ..errors import RegistryValidationError
from .._schema import BracketEntry, FormulaExpression, ParameterDefinition
from ._formula_runtime_support import _evaluate

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
        },
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
        },
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
                    },
                },
            ),
        },
    )


def test_lookup_bracket_by_ccaa_dispatches_to_madrid_when_residence_is_madrid() -> None:
    """Madrid-resident profile routes to the Madrid scale, not Cataluña's.

    Asserts dispatch mechanics: the CCAA binding selects a different bracket
    table than the alternative, so changing the binding changes the result.
    The bracket band constraint confirms the correct row was chosen: the
    Madrid second-band fixed_addition (1058.25) must appear in the result
    because base=20000 exceeds the 12450 threshold, and the marginal rate
    (0.103) is distinct from Cataluña's (0.12).
    """
    base = Decimal("20000")
    madrid_param = _madrid_bracket_param()
    cataluna_param = _cataluna_bracket_param()
    parameters = {
        madrid_param.id: madrid_param,
        cataluna_param.id: cataluna_param,
    }

    madrid_result = _evaluate(
        _dispatch_expression(base),
        parameters=parameters,
        enum_bindings={"renta-2025-profile-tax-residence-ccaa": "madrid"},
    )
    cataluna_result = _evaluate(
        _dispatch_expression(base),
        parameters=parameters,
        enum_bindings={"renta-2025-profile-tax-residence-ccaa": "cataluna"},
    )

    # Dispatch selects different tables — results must differ.
    assert madrid_result != cataluna_result

    # Madrid second band: fixed_addition=1058.25, marginal_rate=0.103.
    # For base=20000 (above 12450 threshold), result must exceed fixed_addition
    # and must be strictly less than the Cataluña result (higher marginal rate).
    assert madrid_result > madrid_param.brackets[1].fixed_addition
    assert madrid_result < cataluna_result

    # Result must be bounded by the bracket band: >= fixed_addition, and
    # less than a full-top-bracket calculation with the Cataluña rate applied.
    madrid_bracket = madrid_param.brackets[1]
    overage = base - madrid_bracket.lower_bound
    expected_marginal = (overage * madrid_bracket.marginal_rate).quantize(Decimal("0.01"))
    assert madrid_result == madrid_bracket.fixed_addition + expected_marginal


def test_lookup_bracket_by_ccaa_dispatches_to_cataluna_when_residence_is_cataluna() -> None:
    """Flipping the binding to Cataluña selects the Cataluña scale.

    Verifies dispatch mechanics: the Cataluña bracket has a higher fixed_addition
    and a higher marginal_rate than Madrid, so the Cataluña result must exceed
    the Madrid result for the same base. The bracket row constraint confirms
    the correct band was applied.
    """
    base = Decimal("20000")
    madrid_param = _madrid_bracket_param()
    cataluna_param = _cataluna_bracket_param()
    parameters = {
        madrid_param.id: madrid_param,
        cataluna_param.id: cataluna_param,
    }

    cataluna_result = _evaluate(
        _dispatch_expression(base),
        parameters=parameters,
        enum_bindings={"renta-2025-profile-tax-residence-ccaa": "cataluna"},
    )

    # Cataluña second band: fixed_addition=1307.25, marginal_rate=0.12.
    cataluna_bracket = cataluna_param.brackets[1]
    overage = base - cataluna_bracket.lower_bound
    expected_marginal = (overage * cataluna_bracket.marginal_rate).quantize(Decimal("0.01"))
    assert cataluna_result == cataluna_bracket.fixed_addition + expected_marginal

    # Cataluña rate > Madrid rate — Cataluña result must be higher.
    madrid_result = _evaluate(
        _dispatch_expression(base),
        parameters=parameters,
        enum_bindings={"renta-2025-profile-tax-residence-ccaa": "madrid"},
    )
    assert cataluna_result > madrid_result


def test_lookup_bracket_by_ccaa_dispatches_with_entry_array_table() -> None:
    """dispatch_table_entries authoring shape produces the same result as dispatch_table dict.

    Verifies that both authoring shapes dispatch to the same bracket table and
    produce identical results — this tests the dispatch indirection, not the
    arithmetic.
    """
    base = Decimal("20000")
    madrid_param = _madrid_bracket_param()
    cataluna_param = _cataluna_bracket_param()
    parameters = {
        madrid_param.id: madrid_param,
        cataluna_param.id: cataluna_param,
    }
    enum_bindings = {"renta-2025-profile-tax-residence-ccaa": "madrid"}

    dict_form_result = _evaluate(
        _dispatch_expression(base),
        parameters=parameters,
        enum_bindings=enum_bindings,
    )

    entry_array_expression = FormulaExpression.model_validate(
        {
            "op": "lookup_bracket_by_ccaa",
            "args": (
                {"literal": base},
                {"binding": "renta-2025-profile-tax-residence-ccaa"},
                {
                    "dispatch_table_entries": [
                        {"key": "madrid", "parameter": madrid_param.id},
                        {"key": "cataluna", "parameter": cataluna_param.id},
                    ],
                },
            ),
        },
    )
    entry_array_result = _evaluate(
        entry_array_expression,
        parameters=parameters,
        enum_bindings=enum_bindings,
    )

    # Both authoring shapes must dispatch to the same table and produce identical output.
    assert dict_form_result == entry_array_result


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
        },
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
            },
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
