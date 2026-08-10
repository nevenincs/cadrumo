"""Neutral application contracts shared by reset and bucket deletion."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG
from ..core.identity import ContentDigest


class BucketDeletionFingerprint(BaseModel):
    """Structured fold of observed deletion-relevant bucket contents.

    The fingerprint is neither a revision lock nor proof recorded by a reset
    journal.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=1, ge=1)
    digest: ContentDigest
    manifest_digest: ContentDigest
    file_count: int = Field(ge=1)
    total_bytes: int = Field(ge=0)


__all__ = ["BucketDeletionFingerprint"]
