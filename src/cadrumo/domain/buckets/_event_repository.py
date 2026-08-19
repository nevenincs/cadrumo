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

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from ._errors import BucketEventValidationError, BucketsError
from ._event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ._protocols import BucketEventHistoryRepositoryProtocol

if TYPE_CHECKING:
    from ...core.secure_object_write import SecureObjectWrite


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

    That is what this always claimed and what it now does. It previously
    assigned unconditionally, which is indistinguishable from collapsing for
    an identical event -- and that equivalence is exactly why the gap held.
    ``payload_version`` is the one field :func:`derive_bucket_event_id` does
    not hash, so two events could share an id while disagreeing about their
    payload contract, and the later one silently replaced an immutable audit
    revision. The catalogue afterwards looked like one content-addressed
    record, so nothing downstream could tell a revision had been erased.

    A colliding id carrying a different version fails closed rather than
    being folded in. Deriving the id from the version instead would make the
    two records distinct, but then a caller that merely mis-stated the
    version would append a duplicate of an event that already exists -- a
    quieter wrong answer than a refusal naming both versions.
    """
    existing = catalogue.events.get(event.event_id)
    if existing is not None:
        if existing == event:
            return catalogue
        raise BucketEventValidationError(
            translated_message="errors.error.error_storage_bucket",
            context={
                "event_id": str(event.event_id),
                "recorded_payload_version": existing.payload_version,
                "offered_payload_version": event.payload_version,
                "payload_versions_agree": False,
            },
        )
    mapping = dict(catalogue.events)
    mapping[event.event_id] = event
    return BucketEventHistoryCatalogue(events=mapping)


def bucket_event_history_write(
    repository: BucketEventHistoryRepositoryProtocol,
    events: tuple[BucketEvent, ...],
) -> SecureObjectWrite:
    """Return the catalogue write appending ``events``, without committing it.

    The commit half of the co-emission pattern :func:`build_bucket_event`
    exists for. A mutation that saves its state and emits afterwards can come
    to rest durable-but-unrecorded -- the state survives while the history has
    no matching entry and no retryable marker names the gap. Folding this
    write into the owning catalogue's batch puts the state and the event it
    promises in one SQL unit of work, so neither can land without the other.

    Appending is idempotent on content, so re-deriving the same event
    collapses onto the same ``event_id`` rather than duplicating the entry.

    Lives here rather than in any one emitting domain because the shape is not
    domain-specific: every emitter that needs its event to share a transaction
    with its state change needs exactly this, and a per-domain copy is how one
    of them silently drifts from the append contract.
    """
    catalogue = repository.load()
    for event in events:
        catalogue = append_bucket_event(catalogue, event)
    return repository.to_secure_object_write(catalogue)


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
    _append_through_the_guard(repository, lambda current: append_bucket_event(current, event))
    return event


def _append_through_the_guard(
    repository: BucketEventHistoryRepositoryProtocol,
    appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
) -> None:
    """Append through the repository's revision guard when it offers one.

    The catalogue is a singleton row, so appending one event rewrites all of
    them and two concurrent emitters lose one another's event. The loss is
    undetectable after the fact: the events are content-addressed, so every
    survivor is internally consistent and the missing one leaves no gap. An
    append-only audit trail that silently drops entries is worse than one that
    refuses, because it still reads as complete.

    The narrow port promises only ``exists``/``load``/``save``, so an injected
    alternative may offer no guard; that fallback keeps the old behaviour and
    its exposure, and is not reachable from the production repository.
    """
    guarded = getattr(repository, "append_guarded", None)
    if guarded is not None:
        guarded(appender)
        return
    repository.save(appender(repository.load()))


def emit_bucket_events(
    *,
    repository: BucketEventHistoryRepositoryProtocol,
    events: Sequence[BucketEvent],
) -> None:
    """Append every event in ``events`` to the catalogue in ONE round-trip.

    The plural counterpart of :func:`emit_bucket_event`, for a caller that
    records several transitions belonging to one atomic mutation. Emitting
    them one at a time costs a full catalogue load and save per event, and
    the catalogue grows without bound, so an N-event mutation paid N
    decrypt/encrypt cycles over a monotonically larger payload.

    This does NOT collapse the audit trail: each event is appended
    individually through :func:`append_bucket_event`, so N distinct
    transitions remain N distinct catalogue entries with their own
    content-addressed ids. Only the number of catalogue round-trips
    changes. Two byte-identical events still collapse onto one id, exactly
    as they do when emitted separately -- that is the content-addressing
    contract, not an effect of batching.

    Events are derived by the caller (through :func:`build_bucket_event`)
    rather than here: a batch's events differ in type and payload, so there
    is no single set of derive arguments to accept.

    Args:
        repository: Port over the bucket-event-history catalogue.
        events: The already-derived events to append. An empty sequence is
            a no-op and does not touch the catalogue.
    """
    if not events:
        return

    def _append_all(current: BucketEventHistoryCatalogue) -> BucketEventHistoryCatalogue:
        """Append every event to whichever catalogue this attempt was handed."""
        catalogue = current
        for event in events:
            catalogue = append_bucket_event(catalogue, event)
        return catalogue

    _append_through_the_guard(repository, _append_all)


__all__ = [
    "BucketEventHistoryPersistenceError",
    "append_bucket_event",
    "build_bucket_event",
    "emit_bucket_event",
    "emit_bucket_events",
]
