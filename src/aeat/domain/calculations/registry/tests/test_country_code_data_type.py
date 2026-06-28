"""Roundtrip tests for the `country_code` data_type and `CountryCode` alias.

The alias enforces alpha-2 shape (two uppercase ASCII letters).
Membership against the AEAT-supported country list is layered on
through per-casilla `enum` constraints and semantic-role
consistency; this surface validates the shape only.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from .._errors import RegistryValidationError
from .._schema import CasillaDefinition, CountryCode, _validate_country_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_COUNTRY_ADAPTER: TypeAdapter[str] = TypeAdapter(CountryCode)


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "country_test_casilla",
            "number": "01",
            "label": "Codigo pais",
            "section": ("operador",),
            "data_type": data_type,
            "legal_refs": ("ley-37-1992:art-25",),
            "source_refs": ("aeat-modelo-349-instructions",),
        },
    )


class TestCountryCodeAccepts:
    @pytest.mark.parametrize("code", ["ES", "FR", "DE", "IT", "PT", "US", "XK", "GB"])
    def test_alpha_two_codes_accepted(self, code: str) -> None:
        assert _COUNTRY_ADAPTER.validate_python(code) == code


class TestCountryCodeRejects:
    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "E",
            "ESP",
            "es",
            "Es",
            "E1",
            "12",
            "  ES",
            "ES ",
            "ES-1",
        ],
    )
    def test_malformed_rejected_through_adapter(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _COUNTRY_ADAPTER.validate_python(raw)

    def test_non_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _COUNTRY_ADAPTER.validate_python(34)

    def test_lowercase_raises_registry_validation_error_at_validator(self) -> None:
        with pytest.raises(RegistryValidationError):
            _validate_country_code("es")

    def test_non_string_raises_registry_validation_error_at_validator(self) -> None:
        with pytest.raises(RegistryValidationError):
            _validate_country_code(34)


class TestCasillaDefinitionDataType:
    def test_country_code_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("country_code")
        round_tripped = CasillaDefinition.model_validate(casilla.model_dump())
        assert round_tripped.data_type == "country_code"
        assert round_tripped == casilla
