"""Spanish tax-identifier validation (NIF / NIE / CIF).

The Agencia Tributaria's identifier algorithm is shared infrastructure
across multiple subpackages — invoice counterparty checks, encrypted
master-key NIF canaries, sanitiser fixture validation, and CLI
preflight gates. Co-locating the algorithm under :mod:`aeat.core.identity`
gives every caller a public, non-private import path so the layered
restructure is not blocked by subpackage-private bypass imports into
:mod:`aeat.domain.financial.invoices._validators`.
"""

from __future__ import annotations

_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_LEADERS = {"X": "0", "Y": "1", "Z": "2"}
_CIF_LEADERS = "ABCDEFGHJKLMNPQRSUVW"
_CIF_LETTER_CONTROL_LEADERS = set("KPQRSNW")
_CIF_CONTROL_LETTERS = "JABCDEFGHI"


def validate_spanish_tax_id(value: str) -> str:
    """Validate a Spanish NIF, NIE, or CIF and return its canonical form.

    Implements the Agencia Tributaria algorithm:

    * **NIF** — 8 digits followed by a checksum letter drawn from
      ``TRWAGMYFPDXBNJZSQVHLCKE`` indexed by ``number % 23``.
    * **NIE** — a leading ``X``/``Y``/``Z`` substituted with ``0``/``1``/``2``
      before applying the NIF rule.
    * **CIF** — a leading letter from ``ABCDEFGHJKLMNPQRSUVW``, 7 digits, and
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


__all__ = ["validate_spanish_tax_id"]
