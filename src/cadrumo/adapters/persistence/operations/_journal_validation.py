"""Validation records and transition rules for the operation journal."""

from __future__ import annotations

from datetime import datetime
from itertools import pairwise

from pydantic import BaseModel, model_validator

from ....application.operations.models import OperationRevision
from ....application.operations.persistence.events import (
    OperationEvent,
    OperationTerminalEvent,
)
from ....application.operations.persistence.journal import OperationPersistedSnapshot
from ....core.models import STRICT_FROZEN_CONFIG
from ..storage.errors import RepositoryError


def _raise_if(condition: bool, message: str, error_type: type[Exception]) -> None:
    if condition:
        raise error_type(message)


class OperationJournalRecord(BaseModel):
    """One atomic file containing current state and complete ordered history."""

    model_config = STRICT_FROZEN_CONFIG

    snapshot: OperationPersistedSnapshot
    history: tuple[OperationEvent, ...]

    @property
    def operation_id(self) -> str:
        return self.snapshot.operation_id

    @property
    def started_at(self) -> datetime:
        return self.snapshot.started_at

    @model_validator(mode="after")
    def _validate_history(self) -> OperationJournalRecord:
        _raise_if(
            any(event.identity != self.snapshot.identity for event in self.history),
            "operation journal history identity does not match the snapshot",
            ValueError,
        )
        self._validate_history_sequence()
        self._validate_history_timestamps()
        self._validate_history_revisions()
        self._validate_terminal_position()
        self._validate_snapshot_tail()
        return self

    def _validate_history_sequence(self) -> None:
        if not self.history:
            _raise_if(
                self.snapshot.event_cursor != 0,
                "empty operation journal history requires snapshot cursor zero",
                ValueError,
            )
            return
        _raise_if(self.history[0].sequence != 1, "operation journal history must begin at sequence one", ValueError)
        _raise_if(
            any(current.sequence != previous.sequence + 1 for previous, current in pairwise(self.history)),
            "operation journal history sequences must be contiguous",
            ValueError,
        )
        _raise_if(
            self.history[-1].sequence != self.snapshot.event_cursor,
            "operation journal history must end at the snapshot cursor",
            ValueError,
        )

    def _validate_history_timestamps(self) -> None:
        _raise_if(
            any(current.timestamp < previous.timestamp for previous, current in pairwise(self.history)),
            "operation journal history timestamps must be nondecreasing",
            ValueError,
        )

    def _validate_history_revisions(self) -> None:
        if not self.history:
            return
        revisions = tuple(event.revision for event in self.history)
        _raise_if(
            revisions[0] not in {0, 1}, "operation journal history must begin at revision zero or one", ValueError
        )
        _raise_if(
            any(current < previous for previous, current in pairwise(revisions)),
            "operation journal history revisions must be ordered",
            ValueError,
        )
        _raise_if(
            any(revision > self.snapshot.revision for revision in revisions),
            "operation journal history cannot exceed the snapshot revision",
            ValueError,
        )

    def _validate_terminal_position(self) -> None:
        _raise_if(
            any(isinstance(event, OperationTerminalEvent) for event in self.history[:-1]),
            "operation journal terminal event must be final in complete history",
            ValueError,
        )

    def _validate_snapshot_tail(self) -> None:
        if not self.snapshot.events:
            return
        _raise_if(
            self.history[-len(self.snapshot.events) :] != self.snapshot.events,
            "operation journal history tail must exactly match the latest snapshot events",
            ValueError,
        )


def validate_advance(
    current: OperationPersistedSnapshot,
    snapshot: OperationPersistedSnapshot,
    expected_revision: OperationRevision,
) -> None:
    """Validate one compare-and-swap successor against its current snapshot."""
    _validate_advance_revision(current, snapshot, expected_revision)
    _validate_advance_identity(current, snapshot)
    _validate_advance_consumed_interactions(current, snapshot)
    _validate_advance_lifecycle(current)
    _validate_advance_events(current, snapshot)


def _validate_advance_revision(
    current: OperationPersistedSnapshot,
    snapshot: OperationPersistedSnapshot,
    expected_revision: OperationRevision,
) -> None:
    _raise_if(
        expected_revision != current.revision, "operation journal compare-and-swap revision is stale", RepositoryError
    )
    _raise_if(
        snapshot.revision != current.revision + 1,
        "operation journal successor revision must advance exactly once",
        RepositoryError,
    )


def _validate_advance_identity(
    current: OperationPersistedSnapshot,
    snapshot: OperationPersistedSnapshot,
) -> None:
    _raise_if(
        snapshot.identity != current.identity,
        "operation journal transition cannot change operation identity",
        RepositoryError,
    )
    _raise_if(
        snapshot.definition_contract_digest != current.definition_contract_digest,
        "operation journal transition cannot change the definition contract digest",
        RepositoryError,
    )
    _raise_if(
        snapshot.request_reference != current.request_reference,
        "operation journal transition cannot change the request reference",
        RepositoryError,
    )
    _raise_if(
        snapshot.request_storage != current.request_storage
        or snapshot.credential_free_request_json != current.credential_free_request_json,
        "operation journal transition cannot change request storage",
        RepositoryError,
    )
    _raise_if(
        snapshot.secret_requirement != current.secret_requirement,
        "operation journal transition cannot change the secret requirement",
        RepositoryError,
    )
    _raise_if(
        current.executor_entered_at is not None and snapshot.executor_entered_at != current.executor_entered_at,
        "operation journal transition cannot rewrite executor entry",
        RepositoryError,
    )
    _raise_if(
        current.executor_entered_at is None
        and snapshot.executor_entered_at is not None
        and snapshot.lifecycle.value != "running",
        "operation journal executor entry requires running lifecycle",
        RepositoryError,
    )
    _raise_if(
        snapshot.started_at != current.started_at,
        "operation journal transition cannot change the start time",
        RepositoryError,
    )
    _raise_if(
        snapshot.idempotency_claim != current.idempotency_claim,
        "operation journal transition cannot change the idempotency claim",
        RepositoryError,
    )


def _validate_advance_consumed_interactions(
    current: OperationPersistedSnapshot,
    snapshot: OperationPersistedSnapshot,
) -> None:
    consumed_before = current.consumed_interactions
    consumed_after = snapshot.consumed_interactions
    _raise_if(
        consumed_after[: len(consumed_before)] != consumed_before,
        "operation journal transition cannot rewrite consumed interaction history",
        RepositoryError,
    )


def _validate_advance_lifecycle(current: OperationPersistedSnapshot) -> None:
    _raise_if(
        current.lifecycle.value == "terminal",
        "operation journal transition cannot advance a terminal operation",
        RepositoryError,
    )


def _validate_advance_events(
    current: OperationPersistedSnapshot,
    snapshot: OperationPersistedSnapshot,
) -> None:
    if snapshot.events:
        _raise_if(
            snapshot.events[0].sequence != current.event_cursor + 1,
            "operation journal transition event cursor is not contiguous",
            RepositoryError,
        )
        return
    _raise_if(
        snapshot.event_cursor != current.event_cursor,
        "event-free operation transition cannot advance the event cursor",
        RepositoryError,
    )


__all__ = ["OperationJournalRecord", "validate_advance"]
