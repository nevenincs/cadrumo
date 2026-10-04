"""Canonical opaque tax-id tokens for per-perceptor observation rows."""

from __future__ import annotations

from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.i18n.translatable import Translatable as tr
from ...core.identity.tax_id import tax_id_identity_token
from .errors import AggregationValidationError


def hashed_tax_id_token(tax_id: str, *, field_name: str) -> str:
    """Return the sha256 of a tax id's canonical identity token.

    Normalises through the same :func:`tax_id_identity_token` each observation
    model applies on construction, so an object key and its aggregation
    grouping key derive from one identity. The normalisation is idempotent, so
    an observation-sourced tax id passes through unchanged; the blank guard
    remains as a defence for callers that key without an observation.

    Args:
        tax_id: The perceptor's tax id, in any of the forms
            :func:`tax_id_identity_token` accepts.
        field_name: The field name to report in the blank-token refusal, so
            each caller's diagnostic names its own parameter.

    This stays package-private on purpose. The live IVA surface composes the
    same two steps for its own subject ref and deliberately does not call this.
    The two callers want OPPOSITE blank behaviour: refusing is required here,
    where a perceptor with no identifier cannot be keyed, and wrong there, where
    a subjectless row is a legitimate domain value that must still project. A
    shared function cannot both raise and not raise, so that caller would guard
    blank before calling and consume only the hash.

    The return width is the second reason and the sharper one: this returns the
    full digest, while the live ref is truncated, and a truncation width IS an
    identity contract -- two refs compare equal only if every producer cuts them
    identically. A shared function returning full hex leaves that caller cutting
    locally anyway.

    What is left to share is a single expression over
    :func:`tax_id_identity_token`, which is already the one identity authority
    both go through.

    Note for anyone re-opening this: the domain-neutral refusal a relocation
    would need already exists -- :class:`IdentityError` with
    ``errors.identity.document_empty``, shipped in all four catalogues. So "the
    error would leak retenciones vocabulary" is NOT a reason to keep these
    apart, and was wrongly given as one when this note was first written. The
    reasons are the opposite blank contracts and the width.

    Raises:
        AggregationValidationError: ``tax_id`` normalises to a blank token.
    """
    token = tax_id_identity_token(tax_id)
    if not token:
        raise AggregationValidationError(
            tr("aggregation.retenciones.errors.perceptor_nif_blank"),
            context={"field": field_name},
        )
    return sha256_hex(token.encode(UTF_8_ENCODING))


__all__ = ["hashed_tax_id_token"]
