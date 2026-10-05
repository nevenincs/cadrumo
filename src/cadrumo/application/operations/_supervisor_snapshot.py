"""Durable operation snapshot transitions owned by the supervisor."""

from __future__ import annotations

from datetime import datetime

from ...core.operations import OperationEffect, OperationLifecycle
from .interactions import OperationConsumedInteraction, OperationPendingInteraction
from .persistence.events import OperationEvent, OperationPhaseEvent
from .persistence.journal import OperationPersistedSnapshot

_SUSPENDED_LIFECYCLES = frozenset({OperationLifecycle.WAITING_FOR_INTERACTION, OperationLifecycle.WAITING_FOR_EXTERNAL})


def advance_events(
    snapshot: OperationPersistedSnapshot,
    events: tuple[OperationEvent, ...],
    revision: int,
    now: datetime,
) -> tuple[OperationEvent, ...]:
    return tuple(
        event.model_copy(update={"revision": revision, "sequence": snapshot.event_cursor + index + 1, "timestamp": now})
        for index, event in enumerate(events)
    )


def _advance_phase_code(snapshot: OperationPersistedSnapshot, emitted: tuple[OperationEvent, ...]) -> str | None:
    phase_events = tuple(event for event in emitted if isinstance(event, OperationPhaseEvent))
    return snapshot.phase_code if not phase_events else phase_events[-1].phase_code


def _advance_value[T](current: T, requested: T | None) -> T:
    return current if requested is None else requested


def advanced_snapshot(
    snapshot: OperationPersistedSnapshot,
    *,
    revision: int,
    lifecycle: OperationLifecycle,
    now: datetime,
    emitted: tuple[OperationEvent, ...],
    pending: OperationPendingInteraction | None,
    consumed: tuple[OperationConsumedInteraction, ...] | None,
    effect: OperationEffect | None,
    execution_deadline: datetime | None,
    cleanup_deadline: datetime | None,
    cancellation_requested_at: datetime | None,
    cancellation_acknowledged_at: datetime | None,
    cancellation_deferred: bool | None,
    executor_entered_at: datetime | None,
) -> OperationPersistedSnapshot:
    return snapshot.model_copy(
        update={
            "revision": revision,
            "lifecycle": lifecycle,
            "updated_at": now,
            "event_cursor": snapshot.event_cursor + len(emitted),
            "events": emitted,
            "phase_code": _advance_phase_code(snapshot, emitted),
            "pending_interaction": pending,
            "consumed_interactions": _advance_value(snapshot.consumed_interactions, consumed),
            "effect": _advance_value(snapshot.effect, effect),
            "execution_deadline": _advance_value(snapshot.execution_deadline, execution_deadline),
            "cleanup_deadline": _advance_value(snapshot.cleanup_deadline, cleanup_deadline),
            "cancellation_requested_at": _advance_value(
                snapshot.cancellation_requested_at,
                cancellation_requested_at,
            ),
            "cancellation_acknowledged_at": _advance_value(
                snapshot.cancellation_acknowledged_at,
                cancellation_acknowledged_at,
            ),
            "cancellation_deferred": _advance_value(snapshot.cancellation_deferred, cancellation_deferred),
            "executor_entered_at": _advance_value(snapshot.executor_entered_at, executor_entered_at),
        }
    )


def awaits_another_settler(snapshot: OperationPersistedSnapshot) -> bool:
    """Whether a state left by a ``None`` return is settled by something other than the executor."""
    return (
        snapshot.lifecycle in _SUSPENDED_LIFECYCLES
        or snapshot.pending_interaction is not None
        or snapshot.cancellation_requested_at is not None
        or snapshot.lifecycle is OperationLifecycle.TERMINAL
    )
