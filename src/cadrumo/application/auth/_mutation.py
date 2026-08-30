"""Shared append-only bucket-event construction for auth mutations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import NamedTuple

from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType, derive_bucket_event_id


class AuthBucketEventSpec(NamedTuple):
    """One append-only auth bucket event prepared by an application mutation."""

    event_type: BucketEventType
    object_id: str
    payload: Mapping[str, str]
    occurred_at: datetime


def build_auth_bucket_events(
    *,
    bucket_id: str,
    events: tuple[AuthBucketEventSpec, ...],
) -> tuple[BucketEvent, ...]:
    """Build deterministic secret-free auth events for atomic persistence."""
    actor = "operator"
    built: list[BucketEvent] = []
    for event in events:
        payload = dict(event.payload)
        event_id = derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.PROFILE,
            object_id=event.object_id,
            payload=payload,
        )
        built.append(
            BucketEvent(
                event_id=event_id,
                bucket_id=bucket_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PROFILE,
                object_id=event.object_id,
                payload_version=1,
                payload=payload,
            ),
        )
    return tuple(built)


__all__ = ["AuthBucketEventSpec", "build_auth_bucket_events"]
