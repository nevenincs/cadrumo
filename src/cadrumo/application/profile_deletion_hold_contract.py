"""Read-only legal and filing owner projections for profile deletion.

The destructive custody transaction consumes these projections but cannot
create or alter their source facts.  Their distinct legal- and filing-owner
modules own the durable records and the semantic mutations that refresh them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ..core.identity._digest import PrefixedContentDigest
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import validate_utc_aware


class ProfileDeletionHoldOwnerProjection(BaseModel):
    """Authenticated owner result consumed by custody deletion preflight."""

    model_config = STRICT_FROZEN_CONFIG

    owner: Literal["legal", "filing"]
    profile_id: UUID
    blocks_local_deletion: bool
    source_record_id: str = Field(min_length=3, max_length=256)
    source_record_digest: PrefixedContentDigest
    assessed_at: datetime

    @field_validator("source_record_id")
    @classmethod
    def _validate_source_record_id(cls, value: str) -> str:
        if value != value.strip() or any(character in value for character in "\\/\x00"):
            raise ValueError("profile deletion hold source record id must be one canonical identifier")
        return value

    @field_validator("source_record_digest")
    @classmethod
    def _validate_source_record_digest(cls, value: str) -> str:
        if (
            len(value) != 71
            or not value.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in value[7:])
        ):
            raise ValueError("profile deletion hold source record digest must be lowercase sha256")
        return value

    @model_validator(mode="after")
    def _validate_assessed_at(self) -> ProfileDeletionHoldOwnerProjection:
        validate_utc_aware(self.assessed_at)
        return self


__all__ = ["ProfileDeletionHoldOwnerProjection"]
