"""Spanish tax-identifier validation (NIF / NIE / CIF) returning canonical strings.

The Agencia Tributaria's identifier algorithm is shared infrastructure
across multiple subpackages — invoice counterparty checks, encrypted
master-key NIF canaries, sanitiser fixture validation, and CLI preflight
gates. Co-locating the algorithm in :mod:`core.identity` gives
every caller a public, layer-respecting import path.

This module differs from :mod:`core.identity._documents` only in its return
shape: :func:`validate_spanish_tax_id` yields the normalised identifier string,
while :func:`~core.identity.validate_identity` returns the matching
:class:`~core.identity.IdentityDocument` enum member. The shape is the ONLY
difference -- there is one implementation of the AEAT algorithm and one CIF
leader policy, both in :mod:`core.identity._documents`, and this function
delegates to them rather than restating them. It once did restate them, and the
two copies drifted into disagreeing about whether an ``ABEH`` CIF may carry a
letter control; two validators answering one question differently is not a
laxer reading, it is a defect with a second opinion.

Both surfaces raise :class:`~core.identity.IdentityError`; this module also
exports :func:`nif_check_letter` for callers that need the shared NIF/NIE
checksum table directly.
"""

from __future__ import annotations

from ._documents import (
    _CIF_KIND_LETTERS,
    _NIE_PREFIX_MAP,
    _PREFIXED_NIF_LEADERS,
    IdentityError,
    nif_check_letter,
    validate_identity,
)
from ._nif_iva import normalise_nif_iva

SPANISH_TAX_ID_WIDTH = 9
"""Character width of every canonical Spanish NIF, NIE, and CIF.

The width is fixed by the identifier grammar rather than chosen here: a NIF is 8
digits plus a checksum letter, a ``K``/``L``/``M`` NIF and a NIE are a leader
plus 7 digits plus a checksum, and a CIF is a leader plus 7 digits plus a
control. Every branch of :func:`validate_spanish_tax_id` therefore operates on
exactly this many characters, and the function refuses anything else outright.

Exposed as a constant because consumers outside this module need to assert a
slot can hold a tax identifier at all -- a fixed-width AEAT record field bound
to a taxpayer identifier but declared at some other width is holding something
other than that identifier. Those consumers must read the width the validator
actually enforces; a second literal elsewhere can drift from this one silently.
"""



def tax_id_identity_token(value: str) -> str:
    """Return the canonical identity form of a tax identifier, without a checksum claim.

    The one comparison form for tax identifiers whose bearer is not
    guaranteed to be Spanish -- a Modelo 190 perceptor may be non-resident
    and carry a foreign identifier, so :func:`validate_spanish_tax_id`'s
    checksum gate would refuse a legitimately declared row. This function
    answers only "are these two identifiers the same identifier", which is
    what grouping keys, distinct counts, and storage object keys need.

    Normalisation is trim-and-uppercase and nothing more: it is idempotent,
    so a value already in canonical form is returned unchanged, and it never
    silently merges two identifiers that differ in their characters.

    Applying it at the model boundary AND at the storage key is the point:
    when an aggregator groups by the raw value while the repository keys by a
    normalised one, two canonically-equal identifiers become two rollups but
    one stored row, so the declared distinct count and the persisted evidence
    disagree.

    Args:
        value: Raw tax identifier as declared.

    Returns:
        The trimmed, uppercased identifier.
    """
    return value.strip().upper()


def same_tax_identifier(left: str | None, right: str | None) -> bool:
    """Return whether two declared identifiers name the same bearer.

    The one "is this the same identifier" predicate. It asserts **no checksum**,
    which is the whole point: the question is identity, not validity, so a
    foreign identifier, or a Spanish one whose control character does not check
    out, must still be comparable. A comparison routed through
    :func:`validate_spanish_tax_id` answers ``False`` for both of those by
    returning nothing to compare, which reads as "different bearer" when the
    truth is "unverifiable identifier".

    Comparison is on the separator-stripped form
    (:func:`~core.identity.normalise_nif_iva`), so a printed ``B-1234567-4``
    matches a stored ``B12345674``. That is deliberately looser than
    :func:`tax_id_identity_token`, which stays trim-and-uppercase because it
    keys stored objects and must never merge two characters-differ identifiers
    into one row; this predicate keys nothing.

    Args:
        left: One identifier as declared, or ``None``.
        right: The other identifier as declared, or ``None``.

    Returns:
        ``True`` only when both sides carry a non-blank value and those values
        are the same identifier. An absent or blank side answers ``False``:
        absence is not a match, and this predicate must never turn "nothing to
        compare" into "the same".
    """
    if left is None or right is None:
        return False
    left_token = normalise_nif_iva(left)
    right_token = normalise_nif_iva(right)
    if not left_token or not right_token:
        return False
    return left_token == right_token


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
        The identifier in the package's separator-stripped normal form --
        :func:`~core.identity.normalise_nif_iva`, the same form
        :func:`same_tax_identifier` compares on, so a printed ``B-1234567-4``
        and a stored ``B12345674`` validate to one string rather than two.

    Raises:
        IdentityError: If the identifier is malformed or the checksum fails.
    """
    normalized = normalise_nif_iva(value)
    if not normalized:
        raise IdentityError(
            "tax identifier is empty",
            translated_message="errors.identity.document_empty",
        )
    if len(normalized) == 11 and normalized.startswith("ES"):
        normalized = normalized[2:]
    if len(normalized) != SPANISH_TAX_ID_WIDTH:
        raise IdentityError(
            f"tax identifier {normalized!r} must be exactly {SPANISH_TAX_ID_WIDTH} characters, got {len(normalized)}",
            translated_message="errors.identity.tax_id_invalid_length",
            context={"candidate": normalized, "length": len(normalized)},
        )

    leader = normalized[0]
    recognised = (
        leader.isdigit()
        or leader in _PREFIXED_NIF_LEADERS
        or leader in _NIE_PREFIX_MAP
        or leader in _CIF_KIND_LETTERS
    )
    if not recognised:
        raise IdentityError(
            f"tax identifier {normalized!r} does not start with a recognised leader {leader!r}",
            translated_message="errors.identity.tax_id_unrecognised_leader",
            context={"candidate": normalized, "leader": leader},
        )
    validate_identity(normalized)
    return normalized


__all__ = ["nif_check_letter", "tax_id_identity_token", "validate_spanish_tax_id"]
