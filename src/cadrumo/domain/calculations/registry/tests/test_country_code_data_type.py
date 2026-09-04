"""Roundtrip tests for the `country_code` data_type and `CountryCode` alias.

The alias enforces alpha-2 shape (two uppercase ASCII letters).
Membership against the AEAT-supported country list is layered on
through per-casilla `enum` constraints and semantic-role
consistency; this surface validates the shape only.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ..errors import RegistryValidationError
from ..schema import CountryCode
from ..schema_scalars import _validate_country_code
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_COUNTRY_ADAPTER: TypeAdapter[str] = TypeAdapter(CountryCode)


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "country_test_casilla",
            "number": "01",
            "localization_keys": ("test.schema.casilla.label",),
            "section": ("operador",),
            "data_type": data_type,
            "legal_refs": ("ley-37-1992:art-25",),
            "source_refs": ("aeat-modelo-349-instructions",),
        },
    )


class TestCountryCodeAccepts:
    def test_alpha_two_codes_accepted(self) -> None:
        for code in ("ES", "FR", "DE", "IT", "PT", "US", "XK", "GB"):
            assert _COUNTRY_ADAPTER.validate_python(code) == code, code


class TestCountryCodeRejects:
    def test_malformed_rejected_through_adapter(self) -> None:
        cases: tuple[object, ...] = ("", "E", "ESP", "es", "Es", "E1", "12", "  ES", "ES ", "ES-1", 34)

        for raw in cases:
            with pytest.raises(ValidationError):
                _COUNTRY_ADAPTER.validate_python(raw)

    def test_invalid_value_raises_registry_validation_error_at_validator(self) -> None:
        for raw in ("es", 34):
            with pytest.raises(RegistryValidationError):
                _validate_country_code(raw)


class TestCasillaDefinitionDataType:
    def test_country_code_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("country_code")
        round_tripped = CasillaDefinition.model_validate(
            {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
        )
        assert round_tripped.data_type == "country_code"
        assert round_tripped == casilla
