"""NIF / NIE / CIF parser and check-letter validator.

The three document shapes:

* **NIF** (Número de Identificación Fiscal): 8 digits, or a leading
  K/L/M plus 7 digits for natural persons without DNI/NIE, followed by
  1 check letter. Check letter computed from the numeric portion via
  ``"TRWAGMYFPDXBNJZSQVHLCKE"[number % 23]``.
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
:func:`~cadrumo.core.identity.validate_spanish_tax_id` from the sibling tax-id
module.
"""

from __future__ import annotations

import re
from enum import StrEnum

from ..errors.hierarchy import CadrumoError

_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX_MAP = {"X": "0", "Y": "1", "Z": "2"}
_PREFIXED_NIF_LEADERS = "KLM"
"""Natural-person NIF leaders for taxpayers without a DNI or NIE."""
_CIF_KIND_LETTERS = "ABCDEFGHJNPQRSUVW"
"""Closed catalogue of CIF leading kind characters per AEAT current spec (17 letters).

K, L, and M are excluded from CIF because they are current natural-person
NIF prefixes, not legal-entity kind letters. This set is the authoritative
shape gate for legal-entity CIF classification via ``_CIF_PATTERN`` and
:func:`validate_identity`; the string-returning ``validate_spanish_tax_id``
helper uses the same CIF catalogue.
"""

# AEAT publishes a small lookup mapping the CIF kind letter to the
# expected check-character format. Letters that always carry a digit
# check, letters that always carry a letter check, and letters that
# accept either are partitioned here.
_CIF_KIND_DIGIT_ONLY = "ABEH"
"""Kinds whose check character MUST be a digit."""

_CIF_KIND_LETTER_ONLY = "PQRSNW"
"""Kinds whose check character MUST be a letter."""

_CIF_LETTER_TABLE = "JABCDEFGHI"
"""When the check character is a letter, it is the index-th entry of this table."""

_NIF_PATTERN = re.compile(r"^(\d{8})([A-Z])$")
_PREFIXED_NIF_PATTERN = re.compile(r"^([KLM])(\d{7})([A-Z])$")
_NIE_PATTERN = re.compile(r"^([XYZ])(\d{7})([A-Z])$")
_CIF_PATTERN = re.compile(rf"^([{_CIF_KIND_LETTERS}])(\d{{7}})(.)$")


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


class IdentityError(CadrumoError, ValueError):
    """Raised when a candidate string is not a valid Spanish identity document.

    Bound to the registered error code ``INTEGRITY_IDENTITY_DOCUMENT``
    in :data:`cadrumo.core.errors.ERROR_REGISTRY`. Carries a human-readable
    diagnostic that names the failing shape (``NIF``, ``NIE``, ``CIF``)
    and, where relevant, the expected vs observed check character.

    Inherits from :class:`ValueError` so that pydantic's
    :class:`~pydantic.AfterValidator` can wrap it directly into a
    :class:`~pydantic.ValidationError` without a re-raise shim.
    """


def nif_check_letter(number: int) -> str:
    """Return the AEAT NIF / NIE check letter for a numeric body.

    Implements the AEAT control-letter table :data:`_NIF_LETTERS`
    (``TRWAGMYFPDXBNJZSQVHLCKE``) indexed by ``number % 23``. This is the
    single source of the check-letter computation for the whole
    :mod:`cadrumo.core.identity` package; the sibling
    :mod:`cadrumo.core.identity._tax_id` re-exports it rather than
    re-declaring the ``% 23`` expression, and every enum-returning
    validator in this module computes its expected letter through it.
    """
    return _NIF_LETTERS[number % 23]


def _cif_check_value(digits: str) -> int:
    """Return the AEAT CIF Luhn-style check value (0-9) for a 7-digit body.

    For each digit position ``i`` (1-indexed) the running sum is built as:

    * odd positions: ``2 * digit``; if the doubled value is >= 10, sum
      its decimal digits (i.e. ``divmod(2*digit, 10)``).
    * even positions: ``digit`` directly.

    The check value is ``(10 - (sum mod 10)) mod 10``. This kernel returns
    the raw integer; :func:`_validate_cif` renders it as a digit or a letter
    and applies the per-kind acceptance policy. That policy exists once, here,
    and both identity surfaces reach it -- the enum-returning
    :func:`validate_identity` and the string-returning
    :func:`cadrumo.core.identity.validate_spanish_tax_id`.

    Args:
        digits: The 7-digit body of the CIF.

    Returns:
        The check value as an integer in ``range(10)``.
    """
    total = 0
    for index, raw in enumerate(digits, start=1):
        digit = int(raw)
        if index % 2 == 1:
            doubled = digit * 2
            total += doubled // 10 + doubled % 10
        else:
            total += digit
    return (10 - (total % 10)) % 10


def _validate_nif(candidate: str) -> IdentityDocument:
    """Validate a NIF candidate, raising :class:`IdentityError` on mismatch."""
    match = _NIF_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(
            f"tax identifier {candidate!r} is not shaped like a NIF",
            translated_message="errors.identity.nif_invalid_shape",
            context={"candidate": candidate},
        )
    digits, letter = match.group(1), match.group(2)
    expected = nif_check_letter(int(digits))
    if letter != expected:
        raise IdentityError(
            f"NIF checksum mismatch for {digits}: expected check letter {expected!r}, got {letter!r}",
            translated_message="errors.identity.nif_check_letter_mismatch",
            context={"digits": digits, "expected": expected, "got": letter},
        )
    return IdentityDocument.NIF


def _validate_prefixed_nif(candidate: str) -> IdentityDocument:
    """Validate a K/L/M-prefixed NIF candidate."""
    match = _PREFIXED_NIF_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(
            f"tax identifier {candidate!r} is not shaped like a NIF",
            translated_message="errors.identity.nif_invalid_shape",
            context={"candidate": candidate},
        )
    prefix, digits, letter = match.group(1), match.group(2), match.group(3)
    expected = nif_check_letter(int(digits))
    if letter != expected:
        raise IdentityError(
            f"NIF checksum mismatch for {prefix + digits}: expected check letter {expected!r}, got {letter!r}",
            translated_message="errors.identity.nif_check_letter_mismatch",
            context={"digits": prefix + digits, "expected": expected, "got": letter},
        )
    return IdentityDocument.NIF


def _validate_nie(candidate: str) -> IdentityDocument:
    """Validate a NIE candidate, raising :class:`IdentityError` on mismatch."""
    match = _NIE_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(
            f"tax identifier {candidate!r} is not shaped like a NIE",
            translated_message="errors.identity.nie_invalid_shape",
            context={"candidate": candidate},
        )
    prefix, digits, letter = match.group(1), match.group(2), match.group(3)
    numeric_str = _NIE_PREFIX_MAP[prefix] + digits
    expected = nif_check_letter(int(numeric_str))
    if letter != expected:
        raise IdentityError(
            f"NIE checksum mismatch for {prefix + digits}: expected check letter {expected!r}, got {letter!r}",
            translated_message="errors.identity.nie_check_letter_mismatch",
            context={"body": prefix + digits, "expected": expected, "got": letter},
        )
    return IdentityDocument.NIE


def _validate_cif(candidate: str) -> IdentityDocument:
    """Validate a CIF candidate, raising :class:`IdentityError` on mismatch.

    The one home of the CIF leader policy. AEAT partitions the kind letters
    three ways and the partition decides which control characters are legal:
    :data:`_CIF_KIND_DIGIT_ONLY` accepts only the digit form,
    :data:`_CIF_KIND_LETTER_ONLY` only the letter form, and every remaining
    kind accepts either, both being historically in circulation.

    The middle class is the one worth naming. A digit-only kind that also
    accepts the letter form is not a laxer reading of the same rule -- it
    accepts an identifier AEAT rejects, so a counterparty passes the boundary
    here and bounces at the sede with the declaration already built.
    """
    match = _CIF_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(
            f"tax identifier {candidate!r} is not shaped like a CIF",
            translated_message="errors.identity.cif_invalid_shape",
            context={"candidate": candidate},
        )
    kind, digits, check = match.group(1), match.group(2), match.group(3)
    if not check.isalnum():
        raise IdentityError(
            f"CIF checksum control character {check!r} in tax identifier {candidate!r} must be a digit or letter",
            translated_message="errors.identity.cif_control_char_invalid",
            context={"candidate": candidate, "got": check},
        )
    check_int = _cif_check_value(digits)
    expected_digit = str(check_int)
    expected_letter = _CIF_LETTER_TABLE[check_int]
    if kind in _CIF_KIND_DIGIT_ONLY:
        if check != expected_digit:
            raise IdentityError(
                f"CIF checksum mismatch (kind {kind}): expected check digit {expected_digit!r}, got {check!r}",
                translated_message="errors.identity.cif_check_digit_mismatch",
                context={"kind": kind, "expected": expected_digit, "got": check},
            )
    elif kind in _CIF_KIND_LETTER_ONLY:
        if check != expected_letter:
            raise IdentityError(
                f"CIF checksum mismatch (kind {kind}): expected check letter {expected_letter!r}, got {check!r}",
                translated_message="errors.identity.cif_check_letter_mismatch_kind",
                context={"kind": kind, "expected": expected_letter, "got": check},
            )
    elif check not in (expected_digit, expected_letter):
        raise IdentityError(
            f"CIF checksum mismatch (kind {kind}): expected {expected_digit} or "
            f"check letter {expected_letter!r}, got {check!r}",
            translated_message="errors.identity.cif_check_char_mismatch_mixed",
            context={
                "kind": kind,
                "expected": expected_digit,
                "alt": expected_letter,
                "got": check,
            },
        )
    return IdentityDocument.CIF


def validate_identity(candidate: object) -> IdentityDocument:
    """Parse and check-letter-validate a Spanish identity document.

    Disambiguates by leading character: ``K``/``L``/``M`` route to prefixed
    NIF, ``X``/``Y``/``Z`` route to NIE,
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
        raise IdentityError(
            "tax identifier is empty",
            translated_message="errors.identity.document_empty",
        )
    # Try prefixed NIF and NIE first (they have unambiguous prefixes);
    # then CIF (also unambiguous on its leading letter set); then NIF.
    if normalised[0] in _PREFIXED_NIF_LEADERS:
        return _validate_prefixed_nif(normalised)
    if normalised[0] in _NIE_PREFIX_MAP:
        return _validate_nie(normalised)
    if normalised[0] in _CIF_KIND_LETTERS:
        return _validate_cif(normalised)
    return _validate_nif(normalised)
