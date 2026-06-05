"""Unit tests for counterparty identity validators."""

from __future__ import annotations

import pytest

from ....core.identity import IdentityError, validate_spanish_tax_id
from .._validators import validate_country_code, validate_iva_number

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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


def test_validate_spanish_tax_id_accepts_abeh_letter_form() -> None:
    """ABEH CIF leaders historically accept either digit- or letter-control form."""
    # body 1234567 digit-control is 4 (above); letter-control is 'D' — both
    # forms are accepted for A/B/E/H leaders.
    assert validate_spanish_tax_id("B12345674") == "B12345674"
    assert validate_spanish_tax_id("B1234567D") == "B1234567D"


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
    """Invalid checksum characters must raise ``IdentityError``.

    The parametrized inputs route through NIF / NIE / CIF-digit /
    CIF-letter validators which each emit a checksum-specific
    message. The shared ``checksum`` keyword is in every branch's
    raise message; the match= ensures the failure is a checksum
    rejection rather than a shape regex miss.
    """
    with pytest.raises(IdentityError, match=r"checksum"):
        validate_spanish_tax_id(value)


@pytest.mark.parametrize(
    "value",
    ["", "12345", "12345678ZA", "?23456781"],
)
def test_validate_spanish_tax_id_rejects_malformed_shapes(value: str) -> None:
    """Blank, short, long, and non-alphanumeric inputs must be rejected.

    Every shape-level rejection in the tax-id pipeline emits a
    message prefixed with ``tax identifier`` (blank / wrong length /
    unrecognised leader). The match= ensures the failure is a
    shape-level rejection, not a checksum failure.
    """
    with pytest.raises(IdentityError, match=r"tax identifier"):
        validate_spanish_tax_id(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12.345.678-Z", "12345678Z"),
        (" 12-345-678-Z ", "12345678Z"),
        ("B-12345674", "B12345674"),
        ("X.1234567.L", "X1234567L"),
    ],
)
def test_validate_spanish_tax_id_strips_common_separators(value: str, expected: str) -> None:
    """NIF/NIE/CIF inputs commonly carry dots or hyphens and must be normalised."""
    assert validate_spanish_tax_id(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ESB12345674", "B12345674"),
        ("es-b-12345674", "B12345674"),
        ("ES 12345678Z", "12345678Z"),
    ],
)
def test_validate_spanish_tax_id_strips_es_iva_prefix(value: str, expected: str) -> None:
    """Spanish IDs carrying the intra-EU ES prefix must validate equivalently."""
    assert validate_spanish_tax_id(value) == expected


@pytest.mark.parametrize(
    ("value", "country", "expected"),
    [
        ("BE 0123.456.789", "BE", "BE0123456789"),
        ("FR.12.345.678.901", "FR", "FR12345678901"),
    ],
)
def test_validate_iva_number_strips_dot_separators(value: str, country: str, expected: str) -> None:
    """Non-ES IVA numbers frequently carry dot separators and must be normalised."""
    assert validate_iva_number(value, country) == expected


@pytest.mark.parametrize(
    ("value", "country", "expected"),
    [
        ("DE123456789", "DE", "DE123456789"),
        ("FR12345678901", "FR", "FR12345678901"),
        (" de 123456789 ", "de", "DE123456789"),
    ],
)
def test_validate_iva_number_accepts_expected_prefixes(value: str, country: str, expected: str) -> None:
    """Country-prefixed IVA bodies must pass the shape check."""
    assert validate_iva_number(value, country) == expected


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
def test_validate_iva_number_rejects_bad_shapes(value: str, country: str) -> None:
    """Missing or mismatched prefix and out-of-range bodies are rejected.

    Every IVA-number rejection message begins with ``IVA number``;
    the prefix-mismatch and body-shape branches both share the
    keyword so the match= pins rejection by the IVA shape gate
    rather than any unrelated InvoiceValidationError.
    """
    with pytest.raises(ValueError, match=r"IVA number"):
        validate_iva_number(value, country)


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


@pytest.mark.parametrize("value", ["", "E", "ESP", "E3"])
def test_validate_country_code_rejects_invalid_shapes(value: str) -> None:
    """Non-2-letter or non-alphabetic country codes are rejected."""
    with pytest.raises(ValueError, match=r"country code must be an ISO-3166 alpha-2 value"):
        validate_country_code(value)
