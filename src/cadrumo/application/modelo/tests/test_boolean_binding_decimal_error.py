"""Instructive ``--binding`` error for a decimal-encoded boolean flag.

The Modelo 100 estimación-directa modality binding is consumed as a numeric
``1`` / ``0`` operand even though it is semantically a boolean flag. Supplying a
non-numeric value such as ``false`` otherwise produces an opaque "is not a
decimal" refusal. :func:`_decimal_binding_value` teaches the accepted encoding on
failure, enumerating each accepted decimal and its meaning derived from the
binding's boolean selector. These tests exercise the real parsing function with a
real :class:`DataBindingDefinition`, so no registry snapshot load is required.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.errors import resolve_error_message
from ....domain.calculations.registry.schema import DataBindingDefinition
from .._calculate_input import ModeloCalculateDecimalInputError, _decimal_binding_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _boolean_binding() -> DataBindingDefinition:
    return DataBindingDefinition.model_validate(
        {
            "id": "renta-2025-modelo-100-estimacion-directa-es-normal",
            "source": "manual_input",
            "selector": {
                "casilla_id": "0168",
                "data_type": "boolean",
                "true_value": "N",
                "false_value": "S",
            },
            "aggregation": {"op": "copy"},
            "typed_enum": "EstimacionDirectaModalidad",
            "legal_refs": ("ley-35-2006:art-30",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )


def _scalar_binding() -> DataBindingDefinition:
    return DataBindingDefinition.model_validate(
        {
            "id": "renta-2025-scalar-input",
            "source": "manual_input",
            "selector": {"casilla_id": "0003", "data_type": "money"},
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )


def test_valid_boolean_encoding_parses_to_decimal() -> None:
    """A well-formed ``1`` / ``0`` value still parses to a Decimal."""
    assert _decimal_binding_value("1", _boolean_binding()) == Decimal("1")
    assert _decimal_binding_value("0", _boolean_binding()) == Decimal("0")


def test_non_numeric_boolean_value_raises_instructive_error() -> None:
    """A non-numeric value names the accepted 0/1 encoding and each meaning."""
    with pytest.raises(ModeloCalculateDecimalInputError) as exc_info:
        _decimal_binding_value("false", _boolean_binding())

    error = exc_info.value
    message = resolve_error_message(error)
    # The refusal enumerates both accepted decimals and the boolean meaning /
    # underlying casilla token each maps to, all derived from the selector.
    assert "1" in message
    assert "0" in message
    assert "true" in message
    assert "false" in message
    assert "N" in message
    assert "S" in message
    assert error.context is not None
    assert error.context["accepted"] == "1, 0"
    assert error.context["value"] == "false"


def test_non_boolean_binding_keeps_generic_decimal_error() -> None:
    """A scalar binding's bad value keeps the plain not-a-decimal refusal."""
    with pytest.raises(ModeloCalculateDecimalInputError) as exc_info:
        _decimal_binding_value("abc", _scalar_binding())

    error = exc_info.value
    assert error.context is not None
    assert "accepted" not in error.context
    assert error.translated_message == "application.modelo.errors.calculate_decimal_input_invalid"
