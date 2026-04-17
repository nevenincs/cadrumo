"""Counterparty identity validators for invoice records.

These helpers implement the Spanish tax-identity algorithms (NIF, NIE,
CIF) as published by the Agencia Tributaria, plus a light EU-VAT prefix
check for non-ES counterparties and an ISO-3166 alpha-2 country-code
normaliser. Each helper raises :class:`ValueError` on failure so
pydantic surfaces the error as a validation error in the enclosing
``Invoice`` model.
"""

from __future__ import annotations

_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_LEADERS = {"X": "0", "Y": "1", "Z": "2"}
_CIF_LEADERS = "ABCDEFGHJKLMNPQRSUVW"
_CIF_LETTER_CONTROL_LEADERS = set("KPQRSNW")
_CIF_DIGIT_CONTROL_LEADERS = set("ABEH")
_CIF_CONTROL_LETTERS = "JABCDEFGHI"


def validate_country_code(value: str) -> str:
    """Normalise and validate an ISO-3166 alpha-2 country code.

    Args:
        value: Raw country code to validate.

    Returns:
        The uppercased two-letter country code.

    Raises:
        ValueError: If the input is not exactly two alphabetic characters.
    """
    normalized = value.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValueError("country code must be an ISO-3166 alpha-2 value")
    return normalized


def validate_spanish_tax_id(value: str) -> str:
    """Validate a Spanish NIF, NIE, or CIF and return its canonical form.

    Implements the Agencia Tributaria algorithm:

    * **NIF** — 8 digits followed by a checksum letter drawn from
      ``TRWAGMYFPDXBNJZSQVHLCKE`` indexed by ``number % 23``.
    * **NIE** — a leading ``X``/``Y``/``Z`` substituted with ``0``/``1``/``2``
      before applying the NIF rule.
    * **CIF** — a leading letter from ``ABCDEFGHJNPQRSUVW``, 7 digits, and
      a 1-character control.  Leading letters in ``KPQRSNW`` require a
      **letter** control drawn from ``JABCDEFGHI``; leading letters in
      ``ABEH`` require a **digit** control; all other leaders accept
      either form (both historically in circulation).

    Args:
        value: Raw tax identifier to validate.

    Returns:
        The uppercased, whitespace-trimmed identifier.

    Raises:
        ValueError: If the identifier is malformed or the checksum fails.
    """
    normalized = value.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
    if not normalized:
        raise ValueError("tax identifier must not be blank")
    # Strip the ES VAT prefix when present so callers that pass the
    # intra-EU form (e.g. "ESB12345674") hit the same checksum path as
    # the bare domestic form ("B12345674").
    if len(normalized) == 11 and normalized.startswith("ES"):
        normalized = normalized[2:]
    if len(normalized) != 9:
        raise ValueError("tax identifier must be 9 characters long")

    leader = normalized[0]
    if leader.isdigit():
        return _validate_nif(normalized)
    if leader in _NIE_LEADERS:
        return _validate_nie(normalized)
    if leader in _CIF_LEADERS:
        return _validate_cif(normalized)
    raise ValueError("tax identifier has an unrecognised leading character")


def validate_vat_number(value: str, country: str) -> str:
    """Validate a non-ES EU VAT number shape against its country prefix.

    Full per-country checksum validation is out of scope; the helper
    enforces only the leading ISO-2 country prefix plus a 4-20 character
    alphanumeric body.

    Args:
        value: Raw VAT identifier to validate.
        country: ISO-3166 alpha-2 country code already validated.

    Returns:
        The uppercased, whitespace-trimmed VAT identifier.

    Raises:
        ValueError: If the value is malformed or the prefix does not match
            ``country``.
    """
    normalized = value.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
    if not normalized:
        raise ValueError("VAT number must not be blank")
    country_upper = country.strip().upper()
    if not normalized.startswith(country_upper):
        raise ValueError("VAT number must start with the counterparty country ISO-2 prefix")
    body = normalized[len(country_upper) :]
    if not (4 <= len(body) <= 20) or not body.isalnum():
        raise ValueError("VAT number body must be 4-20 alphanumeric characters")
    return normalized


def _validate_nif(value: str) -> str:
    digits = value[:8]
    control = value[8]
    if not digits.isdigit() or not control.isalpha():
        raise ValueError("NIF must be 8 digits followed by a checksum letter")
    expected = _NIF_LETTERS[int(digits) % 23]
    if control != expected:
        raise ValueError("NIF checksum letter is invalid")
    return value


def _validate_nie(value: str) -> str:
    leader = value[0]
    body = value[1:8]
    control = value[8]
    if not body.isdigit() or not control.isalpha():
        raise ValueError("NIE must be a leading X/Y/Z plus 7 digits and a checksum letter")
    substituted = _NIE_LEADERS[leader] + body
    expected = _NIF_LETTERS[int(substituted) % 23]
    if control != expected:
        raise ValueError("NIE checksum letter is invalid")
    return value


def _validate_cif(value: str) -> str:
    leader = value[0]
    digits = value[1:8]
    control = value[8]
    if not digits.isdigit():
        raise ValueError("CIF body must be 7 digits")

    even_sum = sum(int(digits[i]) for i in (1, 3, 5))
    odd_sum_doubled = 0
    for i in (0, 2, 4, 6):
        doubled = int(digits[i]) * 2
        odd_sum_doubled += (doubled // 10) + (doubled % 10)
    total = even_sum + odd_sum_doubled
    digit_control = (10 - (total % 10)) % 10
    letter_control = _CIF_CONTROL_LETTERS[digit_control]

    if leader in _CIF_LETTER_CONTROL_LEADERS:
        if not control.isalpha() or control != letter_control:
            raise ValueError("CIF letter-control checksum is invalid")
    elif leader in _CIF_DIGIT_CONTROL_LEADERS:
        # ABEH leaders accept either the digit-control form or the
        # letter-control form — both circulated historically.
        if control.isdigit():
            if int(control) != digit_control:
                raise ValueError("CIF digit-control checksum is invalid")
        elif control.isalpha():
            if control != letter_control:
                raise ValueError("CIF letter-control checksum is invalid")
        else:
            raise ValueError("CIF control character must be a digit or uppercase letter")
    else:
        if control.isdigit():
            if int(control) != digit_control:
                raise ValueError("CIF digit-control checksum is invalid")
        elif control.isalpha():
            if control != letter_control:
                raise ValueError("CIF letter-control checksum is invalid")
        else:
            raise ValueError("CIF control character must be a digit or uppercase letter")
    return value
