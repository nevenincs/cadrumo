"""Spanish tax-identifier validation (NIF / NIE / CIF) returning canonical strings.

The Agencia Tributaria's identifier algorithm is shared infrastructure
across multiple subpackages — invoice counterparty checks, encrypted
master-key NIF canaries, sanitiser fixture validation, and CLI preflight
gates. Co-locating the algorithm in :mod:`aeat.core.identity` gives
every caller a public, layer-respecting import path.

This module differs from :mod:`aeat.core.identity._documents` only in its return
shape: :func:`validate_spanish_tax_id` yields the normalised identifier string,
while :func:`~aeat.core.identity.validate_identity` returns the matching
:class:`~aeat.core.identity.IdentityDocument` enum member. Both surfaces raise
:class:`~aeat.core.identity.IdentityError`; this module also exports
:func:`nif_check_letter` for callers that need the shared NIF/NIE checksum
table directly.
"""

from __future__ import annotations

from ._documents import _NIF_LETTERS, IdentityError

_NIE_LEADERS = {"X": "0", "Y": "1", "Z": "2"}
# ``_CIF_LEADERS`` (20 characters) is a historical-tolerance superset of
# ``aeat.core.identity._documents._CIF_KIND_LETTERS`` (17 characters).
# K, L, and M are included here so that ``validate_spanish_tax_id`` accepts
# K/L/M-led CIFs that AEAT's own validator tolerates for legacy entities.
# Those three letters are deliberately absent from ``_CIF_KIND_LETTERS``,
# which is the AEAT current-spec closed catalogue used by ``validate_identity``
# and ``_CIF_PATTERN`` — the authoritative shape gate for new documents.
_CIF_LEADERS = "ABCDEFGHJKLMNPQRSUVW"
_CIF_LETTER_CONTROL_LEADERS = set("KPQRSNW")
_CIF_CONTROL_LETTERS = "JABCDEFGHI"


def nif_check_letter(number: int) -> str:
    """Return the NIF/NIE checksum letter for ``number``.

    Implements the AEAT control-letter table ``TRWAGMYFPDXBNJZSQVHLCKE``
    indexed by ``number % 23``. This is the single source of the table;
    callers generating or validating Spanish identifiers use it rather
    than re-declaring the literal.
    """
    return _NIF_LETTERS[number % 23]


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
        IdentityError: If the identifier is malformed or the checksum fails.
    """
    normalized = value.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
    if not normalized:
        raise IdentityError("tax identifier must not be blank")
    if len(normalized) == 11 and normalized.startswith("ES"):
        normalized = normalized[2:]
    if len(normalized) != 9:
        raise IdentityError("tax identifier must be 9 characters long")

    leader = normalized[0]
    if leader.isdigit():
        return _validate_nif(normalized)
    if leader in _NIE_LEADERS:
        return _validate_nie(normalized)
    if leader in _CIF_LEADERS:
        return _validate_cif(normalized)
    raise IdentityError("tax identifier has an unrecognised leading character")


def _validate_nif(value: str) -> str:
    """Validate a normalised NIF, returning the input or raising :exc:`ValueError`."""
    digits = value[:8]
    control = value[8]
    if not digits.isdigit() or not control.isalpha():
        raise IdentityError("NIF must be 8 digits followed by a checksum letter")
    expected = nif_check_letter(int(digits))
    if control != expected:
        raise IdentityError("NIF checksum letter is invalid")
    return value


def _validate_nie(value: str) -> str:
    """Validate a normalised NIE, returning the input or raising :exc:`ValueError`."""
    leader = value[0]
    body = value[1:8]
    control = value[8]
    if not body.isdigit() or not control.isalpha():
        raise IdentityError("NIE must be a leading X/Y/Z plus 7 digits and a checksum letter")
    substituted = _NIE_LEADERS[leader] + body
    expected = nif_check_letter(int(substituted))
    if control != expected:
        raise IdentityError("NIE checksum letter is invalid")
    return value


def _validate_cif(value: str) -> str:
    """Validate a normalised CIF, returning the input or raising :exc:`ValueError`."""
    leader = value[0]
    digits = value[1:8]
    control = value[8]
    if not digits.isdigit():
        raise IdentityError("CIF body must be 7 digits")

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
            raise IdentityError("CIF letter-control checksum is invalid")
    else:
        if control.isdigit():
            if int(control) != digit_control:
                raise IdentityError("CIF digit-control checksum is invalid")
        elif control.isalpha():
            if control != letter_control:
                raise IdentityError("CIF letter-control checksum is invalid")
        else:
            raise IdentityError("CIF control character must be a digit or uppercase letter")
    return value


__all__ = ["nif_check_letter", "validate_spanish_tax_id"]
