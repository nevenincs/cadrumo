"""Leaf records shared by workflow state and profile-bucket scanning."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ...adapters.persistence.storage.bucket import BucketLifecycleStatus
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import BucketId


class ProfileBucketPointer(BaseModel):
    """Pointer to a secure profile bucket and its operator-facing label."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    label: str = Field(min_length=1, max_length=160)
    status: BucketLifecycleStatus = BucketLifecycleStatus.ACTIVE

    @field_validator("bucket_id", "label")
    @classmethod
    def _trim_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be blank")
        return trimmed


__all__ = ["ProfileBucketPointer"]
