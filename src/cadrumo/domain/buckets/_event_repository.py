"""Domain boundary error, pure helper, and emit primitive for the event catalogue.

:class:`BucketEventHistoryPersistenceError` is the storage-boundary error the
persistence adapter raises when the encrypted
:class:`BucketEventHistoryCatalogue` cannot be loaded or persisted safely;
:func:`append_bucket_event` is the pure insertion helper over a catalogue, and
:func:`emit_bucket_event` is the derive-append-save primitive every emitting
domain shares. The concrete encrypted-SQL repository lives in the persistence
adapter
(:class:`cadrumo.adapters.persistence.profile.buckets.BucketEventHistoryRepository`),
behind :class:`BucketEventHistoryRepositoryProtocol`; this module owns only the
domain error, the pure helper, and the primitive that composes them.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from ._errors import BucketsError
from ._event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ._protocols import BucketEventHistoryRepositoryProtocol


class BucketEventHistoryPersistenceError(BucketsError):
    """Raised when the bucket-event-history catalogue cannot be persisted or loaded.

    This wraps storage-boundary failures from the persistence adapter's
    :class:`cadrumo.adapters.persistence.profile.buckets.BucketEventHistoryRepository`
    while preserving translated recovery context for callers.
    """


def append_bucket_event(catalogue: BucketEventHistoryCatalogue, event: BucketEvent) -> BucketEventHistoryCatalogue:
    """Return a new :class:`BucketEventHistoryCatalogue` with ``event`` inserted.

    Content-addressed: a re-emission of the same :class:`BucketEvent` collapses
    to the same ``event_id`` and the existing entry is left in place.
    """
    mapping = dict(catalogue.events)
    mapping[event.event_id] = event
    return BucketEventHistoryCatalogue(events=mapping)


def build_bucket_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
    payload_version: int,
) -> BucketEvent:
    """Derive one :class:`BucketEvent` without persisting it.

    The derive half of :func:`emit_bucket_event`, split out so a caller that must
    commit the event in the SAME unit of work as the state change it records can
    obtain the event, fold it into a catalogue with :func:`append_bucket_event`,
    and hand the resulting catalogue to
    :meth:`BucketEventHistoryRepositoryProtocol.to_secure_object_write` for
    co-emission. A mutation that saves its catalogues first and emits afterwards
    can come to rest with durable state and no history entry; deriving without
    saving is what lets the two share one transaction.

    Args:
        bucket_id: Owning bucket identifier.
        event_type: The transition being recorded.
        occurred_at: UTC timestamp of the transition. Callers that need a retry to
            collapse onto one entry pass a stored timestamp rather than a fresh
            clock read, since the id is derived from it.
        actor: Actor label; leading and trailing whitespace is stripped.
        object_type: Kind of the affected domain object.
        object_id: Stable identifier of the affected object.
        payload: Compact structured detail. Never secrets or key material.
        payload_version: Schema version of ``payload`` for this event family.

    Returns:
        The derived :class:`BucketEvent`, not yet appended or persisted.
    """
    actor_label = actor.strip()
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor_label,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor_label,
        object_type=object_type,
        object_id=object_id,
        payload_version=payload_version,
        payload=dict(payload),
    )


def emit_bucket_event(
    *,
    repository: BucketEventHistoryRepositoryProtocol,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
    payload_version: int,
) -> BucketEvent:
    """Derive, append, and persist one :class:`BucketEvent`, returning it.

    Every emitting domain shares this primitive rather than re-deriving the
    id-build-append-save sequence, so an emission cannot drift from the
    content-addressed id contract in :func:`derive_bucket_event_id`. The returned
    event is the durable bucket-scoped audit pointer for the mutation; payloads
    stay compact and reference the owning record instead of duplicating it.

    ``payload_version`` is required, not defaulted. It is the ONLY field that does
    not participate in the derived id, so a wrong value cannot be caught by the
    id check and would silently misdeclare the payload contract of already-written
    events. Each emitting domain versions its own payload independently, so there
    is no project-wide default that would be correct here; a domain that wants one
    supplies it in its own narrow wrapper.

    Args:
        repository: Port over the bucket-event-history catalogue.
        bucket_id: Owning bucket identifier.
        event_type: The transition being recorded.
        occurred_at: UTC timestamp of the transition. Callers that need a retry to
            collapse onto one entry pass a stored timestamp rather than a fresh
            clock read, since the id is derived from it.
        actor: Actor label; leading and trailing whitespace is stripped.
        object_type: Kind of the affected domain object.
        object_id: Stable identifier of the affected object.
        payload: Compact structured detail. Never secrets or key material.
        payload_version: Schema version of ``payload`` for this event family.

    Returns:
        The appended :class:`BucketEvent`.
    """
    event = build_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload=payload,
        payload_version=payload_version,
    )
    repository.save(append_bucket_event(repository.load(), event))
    return event


__all__ = [
    "BucketEventHistoryPersistenceError",
    "append_bucket_event",
    "build_bucket_event",
    "emit_bucket_event",
]
