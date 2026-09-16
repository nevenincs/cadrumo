"""Tests for the domain-owned EU NIF-IVA format authority."""

from __future__ import annotations

import pytest

from .....core.identity.nif_iva import normalise_nif_iva
from ..nif_iva_catalogue import nif_iva_format_for_country, resolve_nif_iva_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VALID_AND_INVALID: list[tuple[str, str, str]] = [
    ("AT", "ATU12345678", "AT12345678"),
    ("BE", "BE0123456789", "BE9123456789"),
    ("BG", "BG123456789", "BG1234567"),
    ("CY", "CY12345678L", "CY123456789"),
    ("CZ", "CZ12345678", "CZ1234567"),
    ("DE", "DE123456789", "DE12345678"),
    ("DK", "DK12345678", "DK1234567"),
    ("EE", "EE123456789", "EE12345678"),
    ("FI", "FI12345678", "FI1234567"),
    ("FR", "FR12345678901", "FR1234567890"),
    ("HR", "HR12345678901", "HR1234567890"),
    ("HU", "HU12345678", "HU1234567"),
    ("IE", "IE1234567T", "IE12345678"),
    ("IT", "IT12345678901", "IT1234567890"),
    ("LT", "LT123456789", "LT12345678"),
    ("LU", "LU12345678", "LU1234567"),
    ("LV", "LV12345678901", "LV1234567890"),
    ("MT", "MT12345678", "MT1234567"),
    ("NL", "NL123456789B01", "NL123456789012"),
    ("PL", "PL1234567890", "PL123456789"),
    ("PT", "PT123456789", "PT12345678"),
    ("RO", "RO1234567890", "RO1"),
    ("SE", "SE123456789012", "SE12345678901"),
    ("SI", "SI12345678", "SI1234567"),
    ("SK", "SK1234567890", "SK123456789"),
    ("XI", "XI123456789", "XI1234"),
    ("GR", "EL123456789", "EL12345678"),
]


def test_nif_iva_patterns_match_examples_and_country_cases() -> None:
    for iso_country, valid, invalid in _VALID_AND_INVALID:
        spec = nif_iva_format_for_country(iso_country)
        assert spec is not None, f"no NIF-IVA spec resolved for {iso_country}"
        assert spec.pattern.match(spec.example) is not None
        assert spec.pattern.match(normalise_nif_iva(valid)) is not None, iso_country
        assert spec.pattern.match(normalise_nif_iva(invalid)) is None, iso_country


def test_country_prefix_resolution_handles_greece_spain_and_unknown_codes() -> None:
    greek_prefix = resolve_nif_iva_catalogue().prefix_for_country("GR")
    assert greek_prefix is not None
    assert greek_prefix.value == "EL"
    lower_greek_prefix = resolve_nif_iva_catalogue().prefix_for_country("gr")
    assert lower_greek_prefix is not None
    assert lower_greek_prefix.value == "EL"
    el_prefix = resolve_nif_iva_catalogue().prefix_for_country("EL")
    assert el_prefix is not None
    assert el_prefix.value == "EL"
    assert nif_iva_format_for_country("ES") is None
    assert nif_iva_format_for_country("US") is None
    assert nif_iva_format_for_country("JP") is None
    assert resolve_nif_iva_catalogue().prefix_for_country("ES") is None


def test_normalise_strips_separators_and_uppercases() -> None:
    assert normalise_nif_iva(" be 0123.456.789 ") == "BE0123456789"
    assert normalise_nif_iva("fr-12-345678901") == "FR12345678901"
