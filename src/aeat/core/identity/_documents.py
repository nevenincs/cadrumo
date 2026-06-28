"""NIF / NIE / CIF parser and check-letter validator.

The three document shapes:

* **NIF** (Número de Identificación Fiscal): 8 digits + 1 check letter.
  Used by Spanish nationals. Check letter computed from the numeric
  portion via ``"TRWAGMYFPDXBNJZSQVHLCKE"[number % 23]``.
* **NIE** (Número de Identidad de Extranjero): leading X / Y / Z + 7
  digits + 1 check letter. Used by foreigners resident in Spain. Check
  letter computed by replacing the leading letter with 0 / 1 / 2
  respectively, then applying the same table as NIF.
* **CIF** (Código de Identificación Fiscal): leading letter (A-H, J, N,
  P-S, U, V, W) + 7 digits + 1 check character. Used by legal entities.
  The check character is either a digit or a letter depending on the
  leading kind code; the algorithm is the Luhn-style sum-of-doubled-
  odd-digits method described by AEAT.

The public :func:`validate_identity` parser returns an :class:`IdentityDocument`
member and raises :class:`IdentityError` on malformed input. It accepts mixed
case, trims surrounding whitespace, and rejects values whose check letter does
not match the algorithm, not just shape mismatches. Callers that only need the
canonical string form use
:func:`~aeat.core.identity.validate_spanish_tax_id` from the sibling tax-id
module.
"""

from __future__ import annotations

import re
from enum import StrEnum

from ..errors import AeatError

_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX_MAP = {"X": "0", "Y": "1", "Z": "2"}
_CIF_KIND_LETTERS = "ABCDEFGHJNPQRSUVW"
"""Closed catalogue of CIF leading kind characters per AEAT current spec (17 letters).

K, L, and M are deliberately excluded: they are historical-only forms that
AEAT's validator tolerates for legacy entities but does not assign to new
CIFs.  ``aeat.core.identity._tax_id._CIF_LEADERS`` retains all three as a
historical-tolerance superset so that ``validate_spanish_tax_id`` keeps
accepting K/L/M-led identifiers; this set is the authoritative shape gate
for current-spec document classification via ``_CIF_PATTERN`` and
:func:`validate_identity`.
"""

# AEAT publishes a small lookup mapping the CIF kind letter to the
# expected check-character format. Letters that always carry a digit
# check, letters that always carry a letter check, and letters that
# accept either are partitioned here.
_CIF_KIND_DIGIT_ONLY = "ABEH"
"""Kinds whose check character MUST be a digit."""

_CIF_KIND_LETTER_ONLY = "KPQRSNW"
"""Kinds whose check character MUST be a letter."""

_CIF_LETTER_TABLE = "JABCDEFGHI"
"""When the check character is a letter, it is the index-th entry of this table."""

_NIF_PATTERN = re.compile(r"^(\d{8})([A-Z])$")
_NIE_PATTERN = re.compile(r"^([XYZ])(\d{7})([A-Z])$")
_CIF_PATTERN = re.compile(rf"^([{_CIF_KIND_LETTERS}])(\d{{7}})([0-9A-J])$")


class IdentityDocument(StrEnum):
    """Closed catalogue of recognised Spanish identity-document kinds.

    Attributes:
        NIF: Número de Identificación Fiscal — Spanish nationals.
        NIE: Número de Identidad de Extranjero — foreign residents.
        CIF: Código de Identificación Fiscal — legal entities.
    """

    NIF = "NIF"
    NIE = "NIE"
    CIF = "CIF"


class IdentityError(AeatError, ValueError):
    """Raised when a candidate string is not a valid Spanish identity document.

    Bound to the registered error code ``INTEGRITY_IDENTITY_DOCUMENT``
    in :data:`aeat.core.errors.ERROR_REGISTRY`. Carries a human-readable
    diagnostic that names the failing shape (``NIF``, ``NIE``, ``CIF``)
    and, where relevant, the expected vs observed check character.

    Inherits from :class:`ValueError` so that pydantic's
    :class:`~pydantic.AfterValidator` can wrap it directly into a
    :class:`~pydantic.ValidationError` without a re-raise shim.
    """


def _compute_nif_check_letter(numeric: int) -> str:
    """Return the AEAT NIF check letter for a numeric body.

    The check letter is :data:`_NIF_LETTERS` indexed by ``numeric % 23``.
    """
    return _NIF_LETTERS[numeric % 23]


def _compute_cif_check(kind: str, digits: str) -> str:
    """Compute the CIF check character per AEAT's Luhn-style algorithm.

    For each digit position ``i`` (1-indexed) the running sum is built as:

    * odd positions: ``2 * digit``; if the doubled value is >= 10, sum
      its decimal digits (i.e. ``divmod(2*digit, 10)``).
    * even positions: ``digit`` directly.

    The check value is ``(10 - (sum mod 10)) mod 10``. Whether it is
    rendered as a digit or as :data:`_CIF_LETTER_TABLE` indexed by the
    check value depends on the leading ``kind`` letter.

    Args:
        kind: The CIF leading kind letter.
        digits: The 7-digit body of the CIF.

    Returns:
        The expected check character as a one-character string.
    """
    total = 0
    for index, raw in enumerate(digits, start=1):
        digit = int(raw)
        if index % 2 == 1:
            doubled = digit * 2
            total += doubled // 10 + doubled % 10
        else:
            total += digit
    check_int = (10 - (total % 10)) % 10
    if kind in _CIF_KIND_DIGIT_ONLY:
        return str(check_int)
    if kind in _CIF_KIND_LETTER_ONLY:
        return _CIF_LETTER_TABLE[check_int]
    # Mixed kinds — either digit or letter is acceptable.
    return str(check_int)


def _validate_nif(candidate: str) -> IdentityDocument:
    """Validate a NIF candidate, raising :class:`IdentityError` on mismatch."""
    match = _NIF_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(
            translated_message="errors.identity.nif_invalid_shape",
            context={"candidate": candidate},
        )
    digits, letter = match.group(1), match.group(2)
    expected = _compute_nif_check_letter(int(digits))
    if letter != expected:
        raise IdentityError(
            translated_message="errors.identity.nif_check_letter_mismatch",
            context={"digits": digits, "expected": expected, "got": letter},
        )
    return IdentityDocument.NIF


def _validate_nie(candidate: str) -> IdentityDocument:
    """Validate a NIE candidate, raising :class:`IdentityError` on mismatch."""
    match = _NIE_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(
            translated_message="errors.identity.nie_invalid_shape",
            context={"candidate": candidate},
        )
    prefix, digits, letter = match.group(1), match.group(2), match.group(3)
    numeric_str = _NIE_PREFIX_MAP[prefix] + digits
    expected = _compute_nif_check_letter(int(numeric_str))
    if letter != expected:
        raise IdentityError(
            translated_message="errors.identity.nie_check_letter_mismatch",
            context={"body": prefix + digits, "expected": expected, "got": letter},
        )
    return IdentityDocument.NIE


def _validate_cif(candidate: str) -> IdentityDocument:
    """Validate a CIF candidate, raising :class:`IdentityError` on mismatch."""
    match = _CIF_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(
            translated_message="errors.identity.cif_invalid_shape",
            context={"candidate": candidate},
        )
    kind, digits, check = match.group(1), match.group(2), match.group(3)
    expected_digit = _compute_cif_check(kind, digits)
    if kind in _CIF_KIND_DIGIT_ONLY:
        if check != expected_digit:
            raise IdentityError(
                translated_message="errors.identity.cif_check_digit_mismatch",
                context={"kind": kind, "expected": expected_digit, "got": check},
            )
    elif kind in _CIF_KIND_LETTER_ONLY:
        if check != expected_digit:
            raise IdentityError(
                translated_message="errors.identity.cif_check_letter_mismatch_kind",
                context={"kind": kind, "expected": expected_digit, "got": check},
            )
    else:
        # Mixed kind: accept either the digit form or the corresponding letter form.
        check_int = int(expected_digit)
        if check != expected_digit and check != _CIF_LETTER_TABLE[check_int]:
            raise IdentityError(
                translated_message="errors.identity.cif_check_char_mismatch_mixed",
                context={
                    "kind": kind,
                    "expected": expected_digit,
                    "alt": _CIF_LETTER_TABLE[check_int],
                    "got": check,
                },
            )
    return IdentityDocument.CIF


def validate_identity(candidate: object) -> IdentityDocument:
    """Parse and check-letter-validate a Spanish identity document.

    Disambiguates by leading character: ``X``/``Y``/``Z`` route to NIE,
    leading letters in :data:`_CIF_KIND_LETTERS` route to CIF, and
    everything else is attempted as NIF. The check-letter / check-digit
    algorithm is then applied for the chosen shape and the parsed
    :class:`IdentityDocument` is returned.

    Args:
        candidate: A free-form candidate value. Strings tolerate surrounding
            whitespace, dashes, spaces, and casing; non-string values are
            rejected with a typed :class:`IdentityError`.

    Returns:
        The matching :class:`IdentityDocument` enum member.

    Raises:
        IdentityError: When ``candidate`` is not a string, is empty, or
            does not match any valid shape, or when the check letter or
            digit fails the AEAT algorithm.
    """
    if not isinstance(candidate, str):
        raise IdentityError(
            translated_message="errors.identity.validate_expects_str",
            context={"got_type": type(candidate).__name__},
        )
    normalised = candidate.strip().upper().replace("-", "").replace(" ", "")
    if not normalised:
        raise IdentityError(translated_message="errors.identity.document_empty")
    # Try NIE first (it has the unambiguous X/Y/Z prefix); then CIF
    # (also unambiguous on its leading letter set); then NIF.
    if normalised[0] in "XYZ":
        return _validate_nie(normalised)
    if normalised[0] in _CIF_KIND_LETTERS:
        return _validate_cif(normalised)
    return _validate_nif(normalised)
