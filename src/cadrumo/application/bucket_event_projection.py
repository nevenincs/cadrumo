"""Closed public projection of canonical bucket events across operations."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..core.hex import Hex64Str
from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..domain.buckets.event import (
    BUCKET_ACTOR_LABEL_MAX_LENGTH,
    BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH,
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
)


class BucketEventDetail(BaseModel):
    """One canonical event payload entry in a closed public schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    name: str = Field(min_length=1, max_length=64)
    value: str = Field(max_length=BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH)


class BucketEventProjection(BaseModel):
    """Exact canonical event facts without an open JSON object branch."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    event_id: Hex64Str
    bucket_id: UUID
    event_type: BucketEventType
    occurred_at: datetime
    actor: str = Field(min_length=1, max_length=BUCKET_ACTOR_LABEL_MAX_LENGTH)
    object_type: BucketEventObjectType
    object_id: str = Field(min_length=1, max_length=128)
    payload_version: int = Field(ge=1)
    details: tuple[BucketEventDetail, ...]

    @model_validator(mode="after")
    def _canonical_event(self) -> Self:
        if len({item.name for item in self.details}) != len(self.details):
            raise ValueError("bucket event repeats a payload name")
        event = self.to_event()
        canonical_details = tuple(sorted(event.payload.items()))
        supplied_details = tuple(sorted((item.name, item.value) for item in self.details))
        if (
            event.actor != self.actor
            or event.object_id != self.object_id
            or len(canonical_details) != len(self.details)
            or canonical_details != supplied_details
        ):
            raise ValueError("bucket event projection contains noncanonical facts")
        return self

    @classmethod
    def from_event(cls, event: BucketEvent) -> BucketEventProjection:
        """Copy every canonical event fact, preserving its derived identity."""
        return cls(
            event_id=event.event_id,
            bucket_id=UUID(event.bucket_id),
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            actor=event.actor,
            object_type=event.object_type,
            object_id=event.object_id,
            payload_version=event.payload_version,
            details=tuple(BucketEventDetail(name=name, value=value) for name, value in sorted(event.payload.items())),
        )

    def to_event(self) -> BucketEvent:
        """Revalidate the canonical content-addressed event on reconstruction."""
        return BucketEvent(
            event_id=self.event_id,
            bucket_id=str(self.bucket_id),
            event_type=self.event_type,
            occurred_at=self.occurred_at,
            actor=self.actor,
            object_type=self.object_type,
            object_id=self.object_id,
            payload_version=self.payload_version,
            payload={item.name: item.value for item in self.details},
        )


__all__ = ["BucketEventDetail", "BucketEventProjection"]
