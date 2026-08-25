"""Roundtrip tests for the `iban` data_type and `IbanString` alias.

The validator enforces ISO 13616 shape (country code + check digits
+ BBAN, total 15-34 chars) and the mod-97 residue check. Inputs are
normalised by stripping whitespace and hyphens and uppercasing.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ..errors import RegistryValidationError
from ..schema import CasillaDefinition, IbanString, _validate_iban_string

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_IBAN_ADAPTER: TypeAdapter[str] = TypeAdapter(IbanString)


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "iban_test_casilla",
            "number": "01",
            "localization_keys": ("test.schema.casilla.label",),
            "section": ("declarante", "pago"),
            "data_type": data_type,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-modelo-303-instructions",),
        },
    )


class TestIbanStringAccepts:
    def test_known_valid_ibans_accepted(self) -> None:
        cases = (
            ("ES9121000418450200051332", "ES9121000418450200051332"),
            ("GB82WEST12345698765432", "GB82WEST12345698765432"),
            ("DE89370400440532013000", "DE89370400440532013000"),
            ("FR1420041010050500013M02606", "FR1420041010050500013M02606"),
        )

        for raw, canonical in cases:
            assert _IBAN_ADAPTER.validate_python(raw) == canonical, raw

    def test_normalisation_strips_punctuation(self) -> None:
        cases = (
            ("  es9121000418450200051332  ", "ES9121000418450200051332"),
            ("ES91-2100-0418-45-0200051332", "ES9121000418450200051332"),
            ("ES91 2100 0418 4502 0005 1332", "ES9121000418450200051332"),
        )

        for raw, canonical in cases:
            assert _IBAN_ADAPTER.validate_python(raw) == canonical, raw


class TestIbanStringRejects:
    def test_invalid_ibans_rejected_through_adapter(self) -> None:
        cases: tuple[object, ...] = (
            "",
            "ES",
            "ES91",
            "1234567890",
            "es9121000418450200051333",  # wrong checksum
            "ES9921000418450200051332",  # wrong check digits
            "@@@@@@@@@@@@@@@@",
            "ES9121000418450200051332EXTRA",  # too long
            123456,
        )

        for raw in cases:
            with pytest.raises(ValidationError):
                _IBAN_ADAPTER.validate_python(raw)

    def test_invalid_ibans_raise_registry_validation_error_at_validator(self) -> None:
        cases = (
            ("", "blank"),
            ("ES9921000418450200051332", "mod-97"),
            ("ES", "ISO 13616"),
        )

        for raw, message in cases:
            with pytest.raises(RegistryValidationError, match=message):
                _validate_iban_string(raw)


class TestCasillaDefinitionDataType:
    def test_iban_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("iban")
        round_tripped = CasillaDefinition.model_validate(
            {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
        )
        assert round_tripped.data_type == "iban"
        assert round_tripped == casilla
