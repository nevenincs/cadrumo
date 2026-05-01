"""NIF / NIE / CIF parser + check-letter validator.

The three document shapes:

- **NIF** (Número de Identificación Fiscal): 8 digits + 1 check
  letter. Used by Spanish nationals. Check letter computed from the
  numeric portion via ``"TRWAGMYFPDXBNJZSQVHLCKE"[number % 23]``.
- **NIE** (Número de Identidad de Extranjero): leading X / Y / Z + 7
  digits + 1 check letter. Used by foreigners resident in Spain.
  Check letter computed by replacing the leading letter with 0 / 1 /
  2 respectively, then applying the same table as NIF.
- **CIF** (Código de Identificación Fiscal): leading letter
  (A-H, J, N, P-S, U, V, W) + 7 digits + 1 check character. Used by
  legal entities. The check character is either a digit or a letter
  depending on the leading kind code; the algorithm is the
  Luhn-style sum-of-doubled-odd-digits method described by AEAT.

The validator accepts mixed case and trims surrounding whitespace.
It rejects values whose check letter does not match the algorithm,
not just shape mismatches.
"""

from __future__ import annotations

import re
from enum import StrEnum

from ..errors import AeatError

_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX_MAP = {"X": "0", "Y": "1", "Z": "2"}
_CIF_KIND_LETTERS = "ABCDEFGHJNPQRSUVW"
"""Closed catalogue of CIF leading kind characters per AEAT spec."""

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
    """Closed catalogue of recognised Spanish identity-document kinds."""

    NIF = "NIF"
    NIE = "NIE"
    CIF = "CIF"


class IdentityError(AeatError):
    """Raised when a candidate string is not a valid Spanish identity document."""


def _compute_nif_check_letter(numeric: int) -> str:
    return _NIF_LETTERS[numeric % 23]


def _compute_cif_check(kind: str, digits: str) -> str:
    """Compute the CIF check character per AEAT's Luhn-style algorithm.

    For each digit position ``i`` (1-indexed), sum is built as:
      - odd positions: ``2 * digit``; if the doubled value is >= 10,
        sum its decimal digits (i.e. ``divmod(2*digit, 10)``).
      - even positions: ``digit`` directly.

    The check value is ``(10 - (sum mod 10)) mod 10``. Whether it is
    rendered as a digit or as ``_CIF_LETTER_TABLE[check]`` depends on
    the leading ``kind`` letter.
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
    match = _NIF_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(f"not a valid NIF shape: {candidate!r}")
    digits, letter = match.group(1), match.group(2)
    expected = _compute_nif_check_letter(int(digits))
    if letter != expected:
        raise IdentityError(
            f"NIF check letter mismatch: expected {expected!r}, got {letter!r}",
        )
    return IdentityDocument.NIF


def _validate_nie(candidate: str) -> IdentityDocument:
    match = _NIE_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(f"not a valid NIE shape: {candidate!r}")
    prefix, digits, letter = match.group(1), match.group(2), match.group(3)
    numeric_str = _NIE_PREFIX_MAP[prefix] + digits
    expected = _compute_nif_check_letter(int(numeric_str))
    if letter != expected:
        raise IdentityError(
            f"NIE check letter mismatch: expected {expected!r}, got {letter!r}",
        )
    return IdentityDocument.NIE


def _validate_cif(candidate: str) -> IdentityDocument:
    match = _CIF_PATTERN.match(candidate)
    if match is None:
        raise IdentityError(f"not a valid CIF shape: {candidate!r}")
    kind, digits, check = match.group(1), match.group(2), match.group(3)
    expected_digit = _compute_cif_check(kind, digits)
    if kind in _CIF_KIND_DIGIT_ONLY:
        if check != expected_digit:
            raise IdentityError(
                f"CIF check digit mismatch (digit-only kind {kind!r}): expected {expected_digit!r}, got {check!r}",
            )
    elif kind in _CIF_KIND_LETTER_ONLY:
        if check != expected_digit:
            raise IdentityError(
                f"CIF check letter mismatch (letter-only kind {kind!r}): expected {expected_digit!r}, got {check!r}",
            )
    else:
        # Mixed kind: accept either the digit form or the corresponding letter form.
        check_int = int(expected_digit)
        if check != expected_digit and check != _CIF_LETTER_TABLE[check_int]:
            raise IdentityError(
                f"CIF check character mismatch (mixed kind {kind!r}): "
                f"expected {expected_digit!r} or {_CIF_LETTER_TABLE[check_int]!r}, "
                f"got {check!r}",
            )
    return IdentityDocument.CIF


def validate_identity(candidate: str) -> IdentityDocument:
    """Parse and check-letter-validate a Spanish identity document.

    Args:
        candidate: A free-form string. Surrounding whitespace and
            casing are tolerated; everything else must match one of
            the three canonical shapes.

    Returns:
        The matching :class:`IdentityDocument`.

    Raises:
        IdentityError: If the value does not match any valid shape
            or the check letter / digit fails.
    """
    if not isinstance(candidate, str):
        raise IdentityError(f"validate_identity expects str; got {type(candidate).__name__}")
    normalised = candidate.strip().upper().replace("-", "").replace(" ", "")
    if not normalised:
        raise IdentityError("identity document is empty")
    # Try NIE first (it has the unambiguous X/Y/Z prefix); then CIF
    # (also unambiguous on its leading letter set); then NIF.
    if normalised[0] in "XYZ":
        return _validate_nie(normalised)
    if normalised[0] in _CIF_KIND_LETTERS:
        return _validate_cif(normalised)
    return _validate_nif(normalised)
