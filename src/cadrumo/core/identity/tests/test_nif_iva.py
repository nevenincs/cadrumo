"""Tests for the EU NIF-IVA per-country format authority.

Exercises the central :data:`cadrumo.core.identity.NIF_IVA_FORMATS` table and its
resolution helpers: every Member State accepts a well-formed IVA number and
rejects a structurally malformed one, the Greek ISO/IVA prefix mismatch
(``GR`` -> ``EL``) resolves correctly, and non-EU / Spanish codes carry no
pattern.

The expected valid and invalid shapes are derived from the European Commission
VIES national IVA-number structure rules (Council Directive 2006/112/EC), not
from any runtime output.
"""

from __future__ import annotations

import pytest

from .. import (
    NIF_IVA_FORMATS,
    NifIvaPrefix,
    nif_iva_format_for_country,
    nif_iva_prefix_for_country,
    normalise_nif_iva,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# (iso_country, valid_number, invalid_number) triples grounded in the VIES
# national IVA-number format rules. Each invalid case violates the country's
# published structure (wrong length, missing block, or wrong character class).
_VALID_AND_INVALID: list[tuple[str, str, str]] = [
    ("AT", "ATU12345678", "AT12345678"),  # missing mandatory U block
    ("BE", "BE0123456789", "BE9123456789"),  # first digit must be 0 or 1
    ("BG", "BG123456789", "BG1234567"),  # too short (needs 9-10 digits)
    ("CY", "CY12345678L", "CY123456789"),  # final character must be a letter
    ("CZ", "CZ12345678", "CZ1234567"),  # too short (needs 8-10 digits)
    ("DE", "DE123456789", "DE12345678"),  # 8 digits, needs 9
    ("DK", "DK12345678", "DK1234567"),  # too short
    ("EE", "EE123456789", "EE12345678"),  # too short
    ("FI", "FI12345678", "FI1234567"),  # too short
    ("FR", "FR12345678901", "FR1234567890"),  # body too short
    ("HR", "HR12345678901", "HR1234567890"),  # 10 digits, needs 11
    ("HU", "HU12345678", "HU1234567"),  # too short
    ("IE", "IE1234567T", "IE12345678"),  # final character must be a letter
    ("IT", "IT12345678901", "IT1234567890"),  # 10 digits, needs 11
    ("LT", "LT123456789", "LT12345678"),  # neither 9 nor 12 digits
    ("LU", "LU12345678", "LU1234567"),  # too short
    ("LV", "LV12345678901", "LV1234567890"),  # too short
    ("MT", "MT12345678", "MT1234567"),  # too short
    ("NL", "NL123456789B01", "NL123456789012"),  # missing mandatory B block
    ("PL", "PL1234567890", "PL123456789"),  # 9 digits, needs 10
    ("PT", "PT123456789", "PT12345678"),  # too short
    ("RO", "RO1234567890", "RO1"),  # single digit (needs 2-10)
    ("SE", "SE123456789012", "SE12345678901"),  # 11 digits, needs 12
    ("SI", "SI12345678", "SI1234567"),  # too short
    ("SK", "SK1234567890", "SK123456789"),  # 9 digits, needs 10
    ("XI", "XI123456789", "XI1234"),  # too short for any XI form
    ("GR", "EL123456789", "EL12345678"),  # Greek prefix EL, 8 digits needs 9
]


def test_nif_iva_patterns_match_examples_and_country_cases() -> None:
    """Each Member State's pattern matches well-formed examples and rejects malformed cases."""
    for prefix, spec in NIF_IVA_FORMATS.items():
        assert spec.prefix is prefix
        assert spec.pattern.match(spec.example) is not None, f"{prefix} example {spec.example!r} fails its pattern"

    for iso_country, valid, invalid in _VALID_AND_INVALID:
        spec = nif_iva_format_for_country(iso_country)
        assert spec is not None, f"no NIF-IVA spec resolved for {iso_country}"
        assert spec.pattern.match(normalise_nif_iva(valid)) is not None, iso_country
        assert spec.pattern.match(normalise_nif_iva(invalid)) is None, iso_country


def test_country_prefix_resolution_handles_greece_spain_and_unknown_codes() -> None:
    """Greece resolves to EL; Spain and non-EU countries carry no structural spec."""
    assert nif_iva_prefix_for_country("GR") is NifIvaPrefix.EL
    assert nif_iva_prefix_for_country("gr") is NifIvaPrefix.EL
    assert nif_iva_prefix_for_country("EL") is NifIvaPrefix.EL
    assert nif_iva_format_for_country("ES") is None
    assert nif_iva_format_for_country("US") is None
    assert nif_iva_format_for_country("JP") is None
    assert nif_iva_prefix_for_country("ES") is None


def test_normalise_strips_separators_and_uppercases() -> None:
    """Operator-pasted separators and case are normalised before matching."""
    assert normalise_nif_iva(" be 0123.456.789 ") == "BE0123456789"
    assert normalise_nif_iva("fr-12-345678901") == "FR12345678901"
