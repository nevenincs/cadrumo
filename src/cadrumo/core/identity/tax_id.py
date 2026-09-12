"""Spanish tax-identifier validation (NIF / NIE / CIF) returning canonical strings.

The Agencia Tributaria's identifier algorithm is shared infrastructure
across multiple subpackages — invoice counterparty checks, encrypted
master-key NIF canaries, sanitiser fixture validation, and CLI preflight
gates. Co-locating the algorithm in :mod:`core.identity` gives
every caller a public, layer-respecting import path.

This module differs from :mod:`core.identity.documents` only in its return
shape: :func:`validate_spanish_tax_id` yields the normalised identifier string,
while :func:`~core.identity.documents.validate_identity` returns the matching
:class:`~core.identity.documents.IdentityDocument` enum member. The shape is the ONLY
difference -- there is one implementation of the AEAT algorithm and one CIF
leader policy, both in :mod:`core.identity.documents`, and this function
delegates to them rather than restating them. It once did restate them, and the
two copies drifted into disagreeing about whether an ``ABEH`` CIF may carry a
letter control; two validators answering one question differently is not a
laxer reading, it is a defect with a second opinion.

Both surfaces raise :class:`~core.identity.documents.IdentityError`; the shared NIF/NIE
checksum table is defined by :mod:`core.identity.documents`.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator

from .documents import IdentityError, SpanishTaxIdFormat, validate_identity
from .nif_iva import normalise_nif_iva


def tax_id_identity_token(value: str) -> str:
    """Return the canonical identity form of a tax identifier, without a checksum claim.

    The one comparison form for tax identifiers whose bearer is not
    guaranteed to be Spanish -- a non-resident counterparty may carry a
    foreign identifier, so :func:`validate_spanish_tax_id`'s
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
    (:func:`~core.identity.nif_iva.normalise_nif_iva`), so a printed ``B-1234567-4``
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


def validate_spanish_tax_id(value: str, tax_id_format: SpanishTaxIdFormat) -> str:
    """Validate a Spanish NIF, NIE, or CIF and return its canonical form.

    Args:
        value: Raw tax identifier to validate.
        tax_id_format: Complete authority-supplied format declarations.

    Returns:
        The identifier in the package's separator-stripped normal form --
        :func:`~core.identity.nif_iva.normalise_nif_iva`, the same form
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
    width = tax_id_format.width
    country_prefix = tax_id_format.country_prefix
    prefixed_width = tax_id_format.country_prefixed_width
    strip_width = tax_id_format.country_prefix_strip_width
    if len(normalized) == prefixed_width and normalized.startswith(country_prefix):
        normalized = normalized[strip_width:]
    if len(normalized) != width:
        raise IdentityError(
            f"tax identifier {normalized!r} must be exactly {width} characters, got {len(normalized)}",
            translated_message="errors.identity.tax_id_invalid_length",
            context={"candidate": normalized, "length": len(normalized)},
        )

    try:
        validate_identity(normalized, tax_id_format)
    except IdentityError as exc:
        leader = normalized[0]
        recognised_leader = leader.isdigit() or any(
            leader in leaders
            for leaders in (tax_id_format.prefixed_nif_leaders, tax_id_format.nie_leaders, tax_id_format.cif_leaders)
        )
        if exc.translated_message == "errors.identity.nif_invalid_shape" and not recognised_leader:
            raise IdentityError(
                f"tax identifier {normalized!r} does not start with a recognised leader {leader!r}",
                translated_message="errors.identity.tax_id_unrecognised_leader",
                context={"candidate": normalized, "leader": leader},
            ) from exc
        raise
    return normalized


type TaxIdIdentityToken = Annotated[str, BeforeValidator(tax_id_identity_token)]
"""Canonical identity form of a tax identifier, normalised at the boundary.

Runs :func:`tax_id_identity_token` BEFORE the field's own length constraints,
so a field annotated with it stores the canonical token and any ``min_length``
bound is applied to that token rather than to the raw declaration. Unlike
:data:`~domain.calculations.registry.tax_id_format.SubjectTaxId` it asserts no
checksum, so it fits identifiers whose bearer may be non-resident; use
:data:`~domain.calculations.registry.tax_id_format.SubjectTaxId` where the value
must be a valid Spanish NIF / NIE / CIF.
"""


__all__ = [
    "TaxIdIdentityToken",
    "same_tax_identifier",
    "tax_id_identity_token",
    "validate_spanish_tax_id",
]
