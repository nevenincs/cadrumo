"""Bucket-identity alias for the per-profile storage container.

The bucket is the per-profile persistence container that sits above any
single record domain. Every record-owning domain (transactions,
invoices, attachments, modelo records) and every persistence adapter
that materialises those records consumes a bucket identity at its
boundary; promoting the :data:`BucketId` alias to :mod:`core.identity` lets each
consumer import it without crossing a sibling-domain boundary.

The constraint shape — ``min_length=1``, ``max_length=128``, surrounding
whitespace stripped — pins the bucket identity at the pydantic boundary
so a malformed value is rejected on construction rather than leaking
into persisted records or wire payloads.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints, TypeAdapter, ValidationError

BucketId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Bucket identity (profile UUID or a system-scoped sentinel)."""

_BUCKET_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BucketId)


def canonical_bucket_id(bucket_id: str) -> str:
    """Return the canonical spelling of ``bucket_id``.

    The alias above states what a bucket identity IS; this states it for a
    value that has not passed a pydantic boundary. Callers that key a
    cryptographic or persisted address on a bucket need the same answer the
    storage layer would give, and computing it from a raw string is where the
    two drift apart: a value the storage layer would refuse outright (blank,
    or overlength) still produces a usable key, and a whitespace-wrapped
    spelling of a VALID id yields a different address than its canonical
    spelling -- two buckets to the address, one bucket to every other layer.

    It lives here, beside the alias it defers to, because the rule has no
    owner otherwise: it was previously defined in the storage master-key
    package with no consumer at all, while four separate call sites each kept
    a private copy of it. A shared rule with four copies and no canonical home
    is the shape that lets the copies diverge silently.

    Args:
        bucket_id: A bucket identity as supplied by a caller, in any spelling.

    Returns:
        The value normalized through :data:`BucketId`, so two spellings of one
        bucket compose byte-identical addresses and associated data.

    Raises:
        ValueError: When the value is not a valid bucket identity. Deliberately
            the plain builtin: each caller translates it into its own typed
            refusal, so the shared helper does not impose one surface's error
            class on every other.
    """
    try:
        return _BUCKET_ID_ADAPTER.validate_python(bucket_id)
    except ValidationError as exc:
        raise ValueError("bucket_id is not a canonical bucket identity") from exc


__all__ = ("BucketId", "canonical_bucket_id")
