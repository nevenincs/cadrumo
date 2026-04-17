"""Unit tests for counterparty identity validators."""

from __future__ import annotations

import pytest

from ._validators import validate_country_code, validate_spanish_tax_id, validate_vat_number


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "12345678Z",
        "00000000T",
        "00000001R",
        "00000002W",
    ],
)
def test_validate_spanish_tax_id_accepts_known_valid_nif(value: str) -> None:
    """Canonical NIF letters must pass the checksum algorithm."""
    assert validate_spanish_tax_id(value) == value


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "X1234567L",
        "Y1234567X",
        "Z1234567R",
    ],
)
def test_validate_spanish_tax_id_accepts_known_valid_nie(value: str) -> None:
    """Valid NIE values for each of the X/Y/Z leaders must pass."""
    assert validate_spanish_tax_id(value) == value


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        # body 5881850 → digit-control 1 (Luhn sum over doubled odd positions +
        # even positions = 29).
        "A58818501",
        # body 1234567 → digit-control 4.
        "B12345674",
        "E12345674",
        "H12345674",
    ],
)
def test_validate_spanish_tax_id_accepts_cif_digit_control(value: str) -> None:
    """CIF leaders that mandate a digit control must accept the right digit."""
    assert validate_spanish_tax_id(value) == value


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        # body 1234567 → letter-control 'D' ("JABCDEFGHI"[4]).
        "K1234567D",
        "P1234567D",
        "Q1234567D",
        "R1234567D",
        "S1234567D",
        "N1234567D",
        "W1234567D",
    ],
)
def test_validate_spanish_tax_id_accepts_cif_letter_control(value: str) -> None:
    """CIF leaders in KPQRSNW must require a letter control from the control table."""
    assert validate_spanish_tax_id(value) == value


@pytest.mark.unit
def test_validate_spanish_tax_id_accepts_abeh_letter_form() -> None:
    """ABEH CIF leaders historically accept either digit- or letter-control form."""
    # body 1234567 digit-control is 4 (above); letter-control is 'D' — both
    # forms are accepted for A/B/E/H leaders.
    assert validate_spanish_tax_id("B12345674") == "B12345674"
    assert validate_spanish_tax_id("B1234567D") == "B1234567D"


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "12345678A",
        "X1234567A",
        "Z1234567A",
        "A58818500",
        "K1234567A",
    ],
)
def test_validate_spanish_tax_id_rejects_invalid_checksum(value: str) -> None:
    """Invalid checksum characters must raise ``ValueError``."""
    with pytest.raises(ValueError):
        validate_spanish_tax_id(value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    ["", "12345", "12345678ZA", "?23456781"],
)
def test_validate_spanish_tax_id_rejects_malformed_shapes(value: str) -> None:
    """Blank, short, long, and non-alphanumeric inputs must be rejected."""
    with pytest.raises(ValueError):
        validate_spanish_tax_id(value)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "country", "expected"),
    [
        ("DE123456789", "DE", "DE123456789"),
        ("FR12345678901", "FR", "FR12345678901"),
        (" de 123456789 ", "de", "DE123456789"),
    ],
)
def test_validate_vat_number_accepts_expected_prefixes(value: str, country: str, expected: str) -> None:
    """Country-prefixed VAT bodies must pass the shape check."""
    assert validate_vat_number(value, country) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "country"),
    [
        ("123456789", "DE"),
        ("FR12345678901", "DE"),
        ("DE12", "DE"),
        ("DE123456789123456789123", "DE"),
        ("DE!!!456789", "DE"),
    ],
)
def test_validate_vat_number_rejects_bad_shapes(value: str, country: str) -> None:
    """Missing or mismatched prefix and out-of-range bodies are rejected."""
    with pytest.raises(ValueError):
        validate_vat_number(value, country)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ES", "ES"),
        (" de ", "DE"),
        ("FR", "FR"),
    ],
)
def test_validate_country_code_normalises(value: str, expected: str) -> None:
    """ISO-3166 alpha-2 codes must be trimmed and uppercased."""
    assert validate_country_code(value) == expected


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "E", "ESP", "E3"])
def test_validate_country_code_rejects_invalid_shapes(value: str) -> None:
    """Non-2-letter or non-alphabetic country codes are rejected."""
    with pytest.raises(ValueError):
        validate_country_code(value)
