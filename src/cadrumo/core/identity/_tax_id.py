"""Spanish tax-identifier validation (NIF / NIE / CIF) returning canonical strings.

The Agencia Tributaria's identifier algorithm is shared infrastructure
across multiple subpackages — invoice counterparty checks, encrypted
master-key NIF canaries, sanitiser fixture validation, and CLI preflight
gates. Co-locating the algorithm in :mod:`core.identity` gives
every caller a public, layer-respecting import path.

This module differs from :mod:`core.identity._documents` only in its return
shape: :func:`validate_spanish_tax_id` yields the normalised identifier string,
while :func:`~core.identity.validate_identity` returns the matching
:class:`~core.identity.IdentityDocument` enum member. Both surfaces raise
:class:`~core.identity.IdentityError`; this module also exports
:func:`nif_check_letter` for callers that need the shared NIF/NIE checksum
table directly.
"""

from __future__ import annotations

from ._documents import (
    _CIF_KIND_LETTERS,
    _CIF_LETTER_TABLE,
    IdentityError,
    _cif_check_value,
    nif_check_letter,
)

_NIE_LEADERS = {"X": "0", "Y": "1", "Z": "2"}
_PREFIXED_NIF_LEADERS = {"K", "L", "M"}
_CIF_LEADERS = _CIF_KIND_LETTERS
_CIF_LETTER_CONTROL_LEADERS = set("PQRSNW")


def validate_spanish_tax_id(value: str) -> str:
    """Validate a Spanish NIF, NIE, or CIF and return its canonical form.

    Implements the Agencia Tributaria algorithm:

    * **NIF** — 8 digits, or current ``K``/``L``/``M`` plus 7 digits for
      natural persons without DNI/NIE, followed by a checksum letter drawn
      from ``TRWAGMYFPDXBNJZSQVHLCKE`` indexed by ``number % 23``.
    * **NIE** — a leading ``X``/``Y``/``Z`` substituted with ``0``/``1``/``2``
      before applying the NIF rule.
    * **CIF** — a leading letter from ``ABCDEFGHJNPQRSUVW``, 7 digits, and
      a 1-character control.  Leading letters in ``PQRSNW`` require a
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
        raise IdentityError(translated_message="errors.identity.document_empty")
    if len(normalized) == 11 and normalized.startswith("ES"):
        normalized = normalized[2:]
    if len(normalized) != 9:
        raise IdentityError(
            translated_message="errors.identity.tax_id_invalid_length",
            context={"candidate": normalized, "length": len(normalized)},
        )

    leader = normalized[0]
    if leader.isdigit():
        return _validate_nif(normalized)
    if leader in _PREFIXED_NIF_LEADERS:
        return _validate_prefixed_nif(normalized)
    if leader in _NIE_LEADERS:
        return _validate_nie(normalized)
    if leader in _CIF_LEADERS:
        return _validate_cif(normalized)
    raise IdentityError(
        translated_message="errors.identity.tax_id_unrecognised_leader",
        context={"candidate": normalized, "leader": leader},
    )


def _validate_nif(value: str) -> str:
    """Validate a normalised NIF, returning the input or raising :exc:`ValueError`."""
    digits = value[:8]
    control = value[8]
    if not digits.isdigit() or not control.isalpha():
        raise IdentityError(
            translated_message="errors.identity.nif_invalid_shape",
            context={"candidate": value},
        )
    expected = nif_check_letter(int(digits))
    if control != expected:
        raise IdentityError(
            translated_message="errors.identity.nif_check_letter_mismatch",
            context={"digits": digits, "expected": expected, "got": control},
        )
    return value


def _validate_prefixed_nif(value: str) -> str:
    """Validate a K/L/M-prefixed natural-person NIF."""
    body = value[1:8]
    control = value[8]
    if not body.isdigit() or not control.isalpha():
        raise IdentityError(
            translated_message="errors.identity.nif_invalid_shape",
            context={"candidate": value},
        )
    expected = nif_check_letter(int(body))
    if control != expected:
        raise IdentityError(
            translated_message="errors.identity.nif_check_letter_mismatch",
            context={"digits": value[:8], "expected": expected, "got": control},
        )
    return value


def _validate_nie(value: str) -> str:
    """Validate a normalised NIE, returning the input or raising :exc:`ValueError`."""
    leader = value[0]
    body = value[1:8]
    control = value[8]
    if not body.isdigit() or not control.isalpha():
        raise IdentityError(
            translated_message="errors.identity.nie_invalid_shape",
            context={"candidate": value},
        )
    substituted = _NIE_LEADERS[leader] + body
    expected = nif_check_letter(int(substituted))
    if control != expected:
        raise IdentityError(
            translated_message="errors.identity.nie_check_letter_mismatch",
            context={"body": value[:8], "expected": expected, "got": control},
        )
    return value


def _validate_cif(value: str) -> str:
    """Validate a normalised CIF, returning the input or raising :exc:`ValueError`."""
    leader = value[0]
    digits = value[1:8]
    control = value[8]
    if not digits.isdigit():
        raise IdentityError(
            translated_message="errors.identity.cif_invalid_shape",
            context={"candidate": value},
        )

    digit_control = _cif_check_value(digits)
    letter_control = _CIF_LETTER_TABLE[digit_control]

    if leader in _CIF_LETTER_CONTROL_LEADERS:
        if not control.isalpha() or control != letter_control:
            raise IdentityError(
                translated_message="errors.identity.cif_check_letter_mismatch_kind",
                context={"kind": leader, "expected": letter_control, "got": control},
            )
    else:
        if control.isdigit():
            if int(control) != digit_control:
                raise IdentityError(
                    translated_message="errors.identity.cif_check_char_mismatch_mixed",
                    context={
                        "kind": leader,
                        "expected": str(digit_control),
                        "alt": letter_control,
                        "got": control,
                    },
                )
        elif control.isalpha():
            if control != letter_control:
                raise IdentityError(
                    translated_message="errors.identity.cif_check_char_mismatch_mixed",
                    context={
                        "kind": leader,
                        "expected": str(digit_control),
                        "alt": letter_control,
                        "got": control,
                    },
                )
        else:
            raise IdentityError(
                translated_message="errors.identity.cif_control_char_invalid",
                context={"candidate": value, "got": control},
            )
    return value


__all__ = ["nif_check_letter", "validate_spanish_tax_id"]
