"""Typed public and private contracts for exact-profile history reads."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.buckets.event import BucketEvent, BucketEventType, bucket_event_order_key
from ..bucket_event_projection import BucketEventProjection

_FilterValue = Annotated[str, Field(min_length=1, max_length=4096)]


class ProfileHistoryRequest(BaseModel):
    """An explicit profile target and the existing CLI's inclusive history filters."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    event_types: tuple[BucketEventType, ...] | None = None
    since: datetime | None = None
    until: datetime | None = None
    object_id: _FilterValue | None = None
    actor: _FilterValue | None = None

    @field_validator("since", "until")
    @classmethod
    @pydantic_validation_boundary
    def _filters_are_utc(cls, value: datetime | None) -> datetime | None:
        return validate_utc_aware(value) if value is not None else None

    @model_validator(mode="after")
    def _valid_range(self) -> Self:
        _require_profile_history_range(self.since, self.until)
        return self


class ProfileHistoryProjection(BaseModel):
    """Every canonical event field and the exact filters used to select it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    event_types: tuple[BucketEventType, ...] | None = None
    since: datetime | None = None
    until: datetime | None = None
    object_id: _FilterValue | None = None
    actor: _FilterValue | None = None
    event_count: int = Field(ge=0)
    events: tuple[BucketEventProjection, ...]

    @field_validator("since", "until")
    @classmethod
    @pydantic_validation_boundary
    def _filters_are_utc(cls, value: datetime | None) -> datetime | None:
        return validate_utc_aware(value) if value is not None else None

    @model_validator(mode="after")
    def _exact_filtered_history(self) -> Self:
        _require_profile_history_range(self.since, self.until)
        _require_profile_history_event_inventory(self.event_count, self.events)
        _require_canonical_profile_history_order(self.events)
        for event in self.events:
            _require_event_matches_profile_history(self, event)
        return self


class ProfileHistoryExecutionResult(BaseModel):
    """Private encrypted operand retained until the current result release."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ProfileHistoryProjection


def _require_profile_history_range(since: datetime | None, until: datetime | None) -> None:
    if since is not None and until is not None and since > until:
        raise ValueError("profile history since is after until")


def _require_profile_history_event_inventory(event_count: int, events: tuple[BucketEventProjection, ...]) -> None:
    if event_count != len(events) or len({event.event_id for event in events}) != len(events):
        raise ValueError("profile history count or event identities differ")


def _require_canonical_profile_history_order(events: tuple[BucketEventProjection, ...]) -> None:
    if tuple(sorted(events, key=lambda event: bucket_event_order_key(event.to_event()))) != events:
        raise ValueError("profile history events are not in canonical order")


def _require_event_matches_profile_history(projection: ProfileHistoryProjection, event: BucketEventProjection) -> None:
    _require_history_event_profile(projection.profile_id, event)
    _require_history_event_type(projection.event_types, event)
    _require_history_event_since(projection.since, event)
    _require_history_event_until(projection.until, event)
    _require_history_event_object(projection.object_id, event)
    _require_history_event_actor(projection.actor, event)


def _require_history_event_profile(profile_id: UUID, event: BucketEventProjection) -> None:
    if event.bucket_id != profile_id:
        raise ValueError("profile history event does not match its profile or filters")


def _require_history_event_type(event_types: tuple[BucketEventType, ...] | None, event: BucketEventProjection) -> None:
    if event_types is not None and event.event_type not in event_types:
        raise ValueError("profile history event does not match its profile or filters")


def _require_history_event_since(since: datetime | None, event: BucketEventProjection) -> None:
    if since is not None and event.occurred_at < since:
        raise ValueError("profile history event does not match its profile or filters")


def _require_history_event_until(until: datetime | None, event: BucketEventProjection) -> None:
    if until is not None and event.occurred_at > until:
        raise ValueError("profile history event does not match its profile or filters")


def _require_history_event_object(object_id: str | None, event: BucketEventProjection) -> None:
    if object_id is not None and event.object_id != object_id:
        raise ValueError("profile history event does not match its profile or filters")


def _require_history_event_actor(actor: str | None, event: BucketEventProjection) -> None:
    if actor is not None and event.actor != actor:
        raise ValueError("profile history event does not match its profile or filters")


def event_matches_profile_history_request(event: BucketEvent, payload: ProfileHistoryRequest) -> bool:
    """Apply inclusive profile-history filter bounds to one already scoped event."""
    return not (
        (payload.since is not None and event.occurred_at < payload.since)
        or (payload.until is not None and event.occurred_at > payload.until)
        or (payload.object_id is not None and event.object_id != payload.object_id)
        or (payload.actor is not None and event.actor != payload.actor)
    )


__all__ = [
    "ProfileHistoryExecutionResult",
    "ProfileHistoryProjection",
    "ProfileHistoryRequest",
    "event_matches_profile_history_request",
]
