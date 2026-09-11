"""Application-owned evidence payload contracts.

These records are transport-neutral projections of evidence facts.  An outer
adapter may render them, but the application owns the shape and its digest
constraint so no transport can silently widen the evidence contract.
"""

from __future__ import annotations

from pydantic import NonNegativeInt

from ...core.identity.digest import ContentDigest
from ...core.json_contract import OutputSchema
from ...domain.buckets.event import BucketEventObjectType, BucketObjectId


class EvidenceRecordRefPayload(OutputSchema):
    """One record reference entry inside an evidence bundle manifest."""

    object_type: BucketEventObjectType
    object_id: BucketObjectId
    content_sha256: ContentDigest
    payload_size_bytes: NonNegativeInt


__all__ = ["EvidenceRecordRefPayload"]
