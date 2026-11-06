"""A ``--binding`` value must be a canonical decimal."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.schema import BindingDefinition
from ..calculate_input_validation import ModeloCalculateDecimalInputError, decimal_binding_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _scalar_binding() -> BindingDefinition:
    return BindingDefinition.model_validate(
        {
            "id": "renta-2025-scalar-input",
            "provider": {
                "kind": "manual_input",
                "casilla_id": "0003",
                "data_type": "money",
            },
            "value": {
                "data_type": "money",
                "channel": "decimal",
            },
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )


def test_a_canonical_binding_value_parses_to_decimal() -> None:
    assert decimal_binding_value("1", _scalar_binding()) == Decimal("1")
    assert decimal_binding_value("0", _scalar_binding()) == Decimal("0")


def test_a_non_numeric_binding_value_is_refused_as_not_a_decimal() -> None:
    """A scalar binding's bad value keeps the plain not-a-decimal refusal."""
    with pytest.raises(ModeloCalculateDecimalInputError) as exc_info:
        decimal_binding_value("abc", _scalar_binding())

    error = exc_info.value
    assert error.context is not None
    assert error.translated_message == "application.modelo.errors.calculate_decimal_input_invalid"
