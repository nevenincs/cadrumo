"""The manual_input validator holds the wire encoding to the value's carrier channel."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..bindings import validate_binding_selector_shape
from .binding_family_support import family_binding

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASILLA = {"kind": "manual_input", "casilla_id": "iva.resultado"}


def test_a_wire_type_on_its_own_channel_passes() -> None:
    binding = family_binding({**_CASILLA, "data_type": "integer"}, data_type="integer", channel="integer")

    assert validate_binding_selector_shape(binding) == []


def test_a_money_quantity_encoded_as_a_decimal_wire_passes() -> None:
    """The wire type describes encoding and the value type the quantity, so they may differ."""
    binding = family_binding({**_CASILLA, "data_type": "decimal"}, data_type="money", channel="decimal")

    assert validate_binding_selector_shape(binding) == []


def test_a_money_wire_on_the_integer_channel_is_refused() -> None:
    binding = family_binding(
        {**_CASILLA, "data_type": "money"},
        data_type="integer",
        channel="integer",
        binding_id="test.manual.money-on-integer",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.manual.money-on-integer" in failures[0]
    assert "'decimal' channel" in failures[0]
    assert "'integer'" in failures[0]


def test_a_text_wire_on_the_boolean_channel_is_refused() -> None:
    binding = family_binding({**_CASILLA, "data_type": "text"}, data_type="boolean", channel="boolean")

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "wire data_type 'text' travels the 'text' channel, not 'boolean'" in failures[0]


_RECORD = {"kind": "manual_input", "record": "cabecera", "field": "importe", "offset": 10, "length": 12}


def test_a_decimal_record_slot_declaring_its_scale_passes() -> None:
    binding = family_binding({**_RECORD, "data_type": "decimal", "decimals": 2})

    assert validate_binding_selector_shape(binding) == []


def test_a_decimal_record_slot_without_a_scale_is_refused_at_hydration() -> None:
    with pytest.raises(ValidationError, match="must declare decimals"):
        family_binding({**_RECORD, "data_type": "decimal"})


def test_a_scale_on_a_non_decimal_wire_is_refused_at_hydration() -> None:
    with pytest.raises(ValidationError, match="declares decimals but its data_type is 'integer'"):
        family_binding({**_RECORD, "data_type": "integer", "decimals": 2}, data_type="integer", channel="integer")
