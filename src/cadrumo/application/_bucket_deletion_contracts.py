"""Neutral application contracts shared by reset and bucket deletion."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class BucketDeletionFingerprint(BaseModel):
    """Structured fold of observed deletion-relevant bucket contents.

    The fingerprint is neither a revision lock nor proof recorded by a reset
    journal.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=1, ge=1)
    digest: str = Field(min_length=64, max_length=64, pattern=_SHA256_PATTERN)
    manifest_digest: str = Field(min_length=64, max_length=64, pattern=_SHA256_PATTERN)
    file_count: int = Field(ge=1)
    total_bytes: int = Field(ge=0)


__all__ = ["BucketDeletionFingerprint"]
