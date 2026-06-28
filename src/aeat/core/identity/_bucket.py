"""Bucket-identity alias for the per-profile storage container.

The bucket is the per-profile persistence container that sits above any
single record domain. Every record-owning domain (transactions,
invoices, attachments, modelo records) and every persistence adapter
that materialises those records consumes a bucket identity at its
boundary; promoting the :data:`BucketId` alias to :mod:`aeat.core.identity` lets each
consumer import it without crossing a sibling-domain boundary.

The constraint shape — ``min_length=1``, ``max_length=128``, surrounding
whitespace stripped — pins the bucket identity at the pydantic boundary
so a malformed value is rejected on construction rather than leaking
into persisted records or wire payloads.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

BucketId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Bucket identity (profile UUID or a system-scoped sentinel)."""

__all__ = ("BucketId",)
