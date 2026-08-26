"""Scalar registry parameters carry dated values before runtime lookup."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema_formula import DatedValue, ParameterDefinition

from ..formula_runtime_ops import resolve_parameter

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ScalarParameterType = Literal["decimal", "money", "integer", "ratio", "text", "boolean"]
_LEGAL_REF = "ley-35-2006:art-63"
_SOURCE_REF = "aeat-renta-2024-manual-parte1"


def _parameter(data_type: _ScalarParameterType, *, values: tuple[DatedValue, ...]) -> ParameterDefinition:
    return ParameterDefinition(
        id=f"test-{data_type}-parameter",
        data_type=data_type,
        unit="eur",
        values=values,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


@pytest.mark.parametrize("data_type", ["decimal", "money", "integer", "ratio", "text", "boolean"])
def test_scalar_parameter_schema_refuses_an_empty_dated_value_table(data_type: _ScalarParameterType) -> None:
    """The authority rejects the shape the runtime cannot resolve."""
    with pytest.raises(ValidationError, match=rf"parameter 'test-{data_type}-parameter' has no dated values"):
        _parameter(data_type, values=())


def test_populated_scalar_parameter_resolves_through_the_runtime_contract() -> None:
    """A valid authority row remains directly resolvable for its date axis."""
    parameter = _parameter(
        "ratio",
        values=(
            DatedValue(
                value=Decimal("19"),
                date_axis="devengo_date",
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
            ),
        ),
    )

    assert resolve_parameter(parameter, {"devengo_date": date(2025, 6, 30)}) == Decimal("19")
