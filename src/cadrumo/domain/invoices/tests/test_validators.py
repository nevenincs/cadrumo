"""Unit tests for counterparty identity validators."""

from __future__ import annotations

import pytest

from ....core.identity import (
    NIF_IVA_FORMATS,
    IdentityError,
    nif_iva_prefix_for_country,
    validate_spanish_tax_id,
)
from ...iva.schema import EUMemberState
from ..validators import validate_country_code, validate_iva_number

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_validate_spanish_tax_id_accepts_known_valid_nif() -> None:
    """Canonical NIF letters must pass the checksum algorithm."""
    values = (
        "12345678Z",
        "00000000T",
        "00000001R",
        "00000002W",
    )

    for value in values:
        assert validate_spanish_tax_id(value) == value


def test_validate_spanish_tax_id_accepts_known_valid_nie() -> None:
    """Valid NIE values for each of the X/Y/Z leaders must pass."""
    values = (
        "X1234567L",
        "Y1234567X",
        "Z1234567R",
    )

    for value in values:
        assert validate_spanish_tax_id(value) == value


def test_validate_spanish_tax_id_accepts_cif_digit_control() -> None:
    """CIF leaders that mandate a digit control must accept the right digit."""
    values = (
        # body 5881850 → digit-control 1 (Luhn sum over doubled odd positions +
        # even positions = 29).
        "A58818501",
        # body 1234567 → digit-control 4.
        "B12345674",
        "E12345674",
        "H12345674",
    )

    for value in values:
        assert validate_spanish_tax_id(value) == value


def test_validate_spanish_tax_id_accepts_cif_letter_control() -> None:
    """CIF leaders in PQRSNW must require a letter control from the control table.

    ``K`` is excluded: it is a current-spec natural-person NIF prefix, not a
    CIF kind letter (see ``cadrumo.core.identity._currentize klm nif validation``).
    """
    values = (
        # body 1234567 → letter-control 'D' ("JABCDEFGHI"[4]).
        "P1234567D",
        "Q1234567D",
        "R1234567D",
        "S1234567D",
        "N1234567D",
        "W1234567D",
    )

    for value in values:
        assert validate_spanish_tax_id(value) == value


def test_validate_spanish_tax_id_accepts_abeh_letter_form() -> None:
    """ABEH CIF leaders historically accept either digit- or letter-control form."""
    # body 1234567 digit-control is 4 (above); letter-control is 'D' — both
    # forms are accepted for A/B/E/H leaders.
    assert validate_spanish_tax_id("B12345674") == "B12345674"
    assert validate_spanish_tax_id("B1234567D") == "B1234567D"


def test_validate_spanish_tax_id_rejects_invalid_checksum() -> None:
    """Invalid checksum characters must raise ``IdentityError``.

    The inputs route through NIF / NIE / CIF-digit / CIF-letter validators
    which each emit a checksum-specific message. The shared ``checksum`` keyword
    is in every branch's raise message; the match= ensures the failure is a
    checksum rejection rather than a shape regex miss.
    """
    values = (
        "12345678A",
        "X1234567A",
        "Z1234567A",
        "A58818500",
        "K1234567A",
    )

    for value in values:
        with pytest.raises(IdentityError, match=r"checksum"):
            validate_spanish_tax_id(value)


def test_validate_spanish_tax_id_rejects_malformed_shapes() -> None:
    """Blank, short, long, and non-alphanumeric inputs must be rejected.

    Every shape-level rejection in the tax-id pipeline emits a
    message prefixed with ``tax identifier`` (blank / wrong length /
    unrecognised leader). The match= ensures the failure is a
    shape-level rejection, not a checksum failure.
    """
    for value in ("", "12345", "12345678ZA", "?23456781"):
        with pytest.raises(IdentityError, match=r"tax identifier"):
            validate_spanish_tax_id(value)


def test_validate_spanish_tax_id_strips_common_separators() -> None:
    """NIF/NIE/CIF inputs commonly carry dots or hyphens and must be normalised."""
    cases = (
        ("12.345.678-Z", "12345678Z"),
        (" 12-345-678-Z ", "12345678Z"),
        ("B-12345674", "B12345674"),
        ("X.1234567.L", "X1234567L"),
    )

    for value, expected in cases:
        assert validate_spanish_tax_id(value) == expected, value


def test_validate_spanish_tax_id_strips_es_iva_prefix() -> None:
    """Spanish IDs carrying the intra-EU ES prefix must validate equivalently."""
    cases = (
        ("ESB12345674", "B12345674"),
        ("es-b-12345674", "B12345674"),
        ("ES 12345678Z", "12345678Z"),
    )

    for value, expected in cases:
        assert validate_spanish_tax_id(value) == expected, value


def test_validate_iva_number_strips_dot_separators() -> None:
    """Non-ES IVA numbers frequently carry dot separators and must be normalised."""
    cases = (
        ("BE 0123.456.789", "BE", "BE0123456789"),
        ("FR.12.345.678.901", "FR", "FR12345678901"),
    )

    for value, country, expected in cases:
        assert validate_iva_number(value, country) == expected, (value, country)


def test_validate_iva_number_accepts_expected_prefixes() -> None:
    """Country-prefixed IVA bodies must pass the shape check."""
    cases = (
        ("DE123456789", "DE", "DE123456789"),
        ("FR12345678901", "FR", "FR12345678901"),
        (" de 123456789 ", "de", "DE123456789"),
    )

    for value, country, expected in cases:
        assert validate_iva_number(value, country) == expected, (value, country)


def test_validate_iva_number_rejects_bad_shapes() -> None:
    """Missing or mismatched prefix and out-of-range bodies are rejected.

    Every IVA-number rejection message begins with ``IVA number``;
    the prefix-mismatch and body-shape branches both share the
    keyword so the match= pins rejection by the IVA shape gate
    rather than any unrelated InvoiceValidationError.
    """
    cases = (
        ("123456789", "DE"),
        ("FR12345678901", "DE"),
        ("DE12", "DE"),
        ("DE123456789123456789123", "DE"),
        ("DE!!!456789", "DE"),
    )

    for value, country in cases:
        with pytest.raises(ValueError, match=r"IVA number"):
            validate_iva_number(value, country)


def test_validate_country_code_normalises() -> None:
    """ISO-3166 alpha-2 codes must be trimmed and uppercased."""
    cases = (
        ("ES", "ES"),
        (" de ", "DE"),
        ("FR", "FR"),
    )

    for value, expected in cases:
        assert validate_country_code(value) == expected, value


def test_validate_country_code_rejects_invalid_shapes() -> None:
    """Non-2-letter or non-alphabetic country codes are rejected."""
    for value in ("", "E", "ESP", "E3"):
        with pytest.raises(ValueError, match=r"country code must be an ISO-3166 alpha-2 value"):
            validate_country_code(value)


def test_validate_iva_number_accepts_wellformed_per_country() -> None:
    """A NIF-IVA matching its Member State's published structure is accepted.

    The Greek case proves the ISO/IVA-prefix mismatch is handled: country
    ``GR`` accepts an ``EL``-prefixed number.
    """
    cases = (
        ("DE123456789", "DE", "DE123456789"),
        ("FR12345678901", "FR", "FR12345678901"),
        ("IT12345678901", "IT", "IT12345678901"),
        ("NL123456789B01", "NL", "NL123456789B01"),
        ("AT U12345678", "AT", "ATU12345678"),
        ("IE 1234567T", "IE", "IE1234567T"),
        ("EL123456789", "GR", "EL123456789"),
        ("XI123456789", "XI", "XI123456789"),
    )

    for value, country, expected in cases:
        assert validate_iva_number(value, country) == expected, (value, country)


def test_validate_iva_number_rejects_malformed_eu_with_instructive_message() -> None:
    """A structurally malformed EU NIF-IVA is refused naming the country and format."""
    cases = (
        ("DE12345678", "DE", "Germany"),  # 8 digits, needs 9 — the round-18 defect case
        ("IT1234567890", "IT", "Italy"),  # 10 digits, needs 11
        ("NL123456789012", "NL", "Netherlands"),  # missing mandatory B block
        ("FR1234567890", "FR", "France"),  # body too short
        ("EL12345678", "GR", "Greece"),  # 8 digits, needs 9
        ("BE9123456789", "BE", "Belgium"),  # first digit must be 0 or 1
    )

    for value, country, country_name in cases:
        with pytest.raises(ValueError) as excinfo:
            validate_iva_number(value, country)
        message = str(excinfo.value)
        assert "IVA number" in message, (value, country)
        assert country_name in message, (value, country)
        # The refusal must name the expected structure, not a bare "invalid".
        assert "expected" in message, (value, country)


def test_validate_iva_number_non_eu_falls_back_to_generic_shape() -> None:
    """Non-EU counterparties carry no published NIF-IVA pattern and use the generic check."""
    cases = (
        ("US123456789", "US", "US123456789"),  # non-EU: generic prefix + body check
        ("CH-12345678", "CH", "CH12345678"),  # Switzerland, non-EU
        ("GB123456789", "GB", "GB123456789"),  # post-Brexit GB has no EU NIF-IVA pattern
    )

    for value, country, expected in cases:
        assert validate_iva_number(value, country) == expected, (value, country)


def test_validate_iva_number_non_eu_generic_still_rejects_bad_shape() -> None:
    """The generic non-EU fallback still rejects a missing prefix or an out-of-range body."""
    with pytest.raises(ValueError, match=r"IVA number"):
        validate_iva_number("123456789", "US")  # no US prefix
    with pytest.raises(ValueError, match=r"IVA number"):
        validate_iva_number("USxx", "US")  # body too short


def test_every_eu_member_state_except_spain_has_a_nif_iva_format() -> None:
    """The format table covers every EU Member State (Greece via EL), excluding Spain.

    Anchored to :class:`cadrumo.domain.iva.EUMemberState` so a future Member State
    addition or withdrawal fails this gate until the central table is updated.
    Spain is intentionally absent — Spanish identifiers use the checksum
    validator, not a structural pattern.
    """
    for member in EUMemberState:
        if member is EUMemberState.ES:
            assert nif_iva_prefix_for_country(member.value) is None
            continue
        prefix = nif_iva_prefix_for_country(member.value.upper())
        assert prefix is not None, f"no NIF-IVA prefix resolves for EU member {member.value}"
        assert prefix in NIF_IVA_FORMATS, f"no NIF-IVA format declared for {prefix}"
