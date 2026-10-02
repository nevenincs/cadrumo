"""Registered calculation inputs preserve raw channels and reject ambiguous facts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ...operations.registry_schema_validation import strict_model_json_schema
from ..calculation_request_fields import ModeloCalculationInputFieldsV1, ModeloCalculationOverride

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_input_channels_roundtrip_without_interpreting_text_or_losing_precision() -> None:
    request = ModeloCalculationInputFieldsV1(
        casilla_overrides=(
            ModeloCalculationOverride(key="tipo_renta", value="01"),
            ModeloCalculationOverride(key="base_imponible", value="0.00001"),
        ),
        binding_overrides=(ModeloCalculationOverride(key="election", value="yes"),),
        prestacion_inss_exenta="0.00",
    )
    strict_model_json_schema(ModeloCalculationInputFieldsV1)
    restored = ModeloCalculationInputFieldsV1.model_validate_json(request.model_dump_json())
    assert restored == request
    assert restored.casilla_overrides[0].value == "01"
    assert restored.casilla_overrides[1].value == "0.00001"
    assert restored.prestacion_inss_exenta == "0.00"


@pytest.mark.parametrize("channel", ["casilla_overrides", "binding_overrides", "relation_overrides"])
def test_duplicate_channel_keys_refuse_before_dictionary_conversion(channel: str) -> None:
    with pytest.raises(ValidationError, match="duplicate keys"):
        ModeloCalculationInputFieldsV1.model_validate_json(
            '{"' + channel + '":[{"key":"same","value":"100"},{"key":"same","value":"0"}]}'
        )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1E+3", "1,00", "+1"])
def test_shortcut_amount_refuses_noncanonical_or_nonfinite_tokens(value: str) -> None:
    with pytest.raises(ValidationError, match="canonical finite decimal text") as error:
        ModeloCalculationInputFieldsV1(prestacion_inss_exenta=value)
    assert "input_value=" not in str(error.value)
