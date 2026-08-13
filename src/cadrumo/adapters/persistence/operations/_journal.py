"""Atomic filesystem implementation of the credential-free operation journal."""

from __future__ import annotations

import os
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import override

from pydantic import BaseModel, model_validator

from ....application.operations import (
    JournalRepositoryBase,
    OperationEvent,
    OperationEventCursor,
    OperationEventStream,
    OperationJournal,
    OperationOwnerLease,
    OperationPersistedSnapshot,
    OperationReplayLimit,
    OperationReplayPage,
    OperationReplayStatus,
    OperationRevision,
    OperationTerminalEvent,
)
from ....core import STRICT_FROZEN_CONFIG, StorageCategory, exclusive_file_lock, storage_location
from ..storage import RepositoryError


class _OperationReplayRequest(BaseModel):
    """Strict adapter-local replay inputs before filesystem access."""

    model_config = STRICT_FROZEN_CONFIG

    cursor: OperationEventCursor
    limit: OperationReplayLimit


class _OperationJournalRecord(BaseModel):
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
    def _validate_history(self) -> _OperationJournalRecord:
        if any(event.identity != self.snapshot.identity for event in self.history):
            raise ValueError("operation journal history identity does not match the snapshot")
        self._validate_history_sequence()
        self._validate_history_timestamps()
        self._validate_history_revisions()
        self._validate_terminal_position()
        self._validate_snapshot_tail()
        return self

    def _validate_history_sequence(self) -> None:
        if not self.history:
            if self.snapshot.event_cursor != 0:
                raise ValueError("empty operation journal history requires snapshot cursor zero")
            return
        if self.history[0].sequence != 1:
            raise ValueError("operation journal history must begin at sequence one")
        if any(current.sequence != previous.sequence + 1 for previous, current in pairwise(self.history)):
            raise ValueError("operation journal history sequences must be contiguous")
        if self.history[-1].sequence != self.snapshot.event_cursor:
            raise ValueError("operation journal history must end at the snapshot cursor")

    def _validate_history_timestamps(self) -> None:
        if any(current.timestamp < previous.timestamp for previous, current in pairwise(self.history)):
            raise ValueError("operation journal history timestamps must be nondecreasing")

    def _validate_history_revisions(self) -> None:
        if not self.history:
            return
        revisions = tuple(event.revision for event in self.history)
        if revisions[0] not in {0, 1}:
            raise ValueError("operation journal history must begin at revision zero or one")
        if any(current < previous or current > previous + 1 for previous, current in pairwise(revisions)):
            raise ValueError("operation journal history revisions must be ordered unit advances")
        if revisions[-1] != self.snapshot.revision:
            raise ValueError("operation journal history must end at the snapshot revision")

    def _validate_terminal_position(self) -> None:
        if any(isinstance(event, OperationTerminalEvent) for event in self.history[:-1]):
            raise ValueError("operation journal terminal event must be final in complete history")

    def _validate_snapshot_tail(self) -> None:
        if not self.snapshot.events:
            if self.history:
                raise ValueError("eventful operation journal history requires a latest snapshot event tail")
            return
        if self.history[-len(self.snapshot.events) :] != self.snapshot.events:
            raise ValueError("operation journal history tail must exactly match the latest snapshot events")


class _SnapshotJournalRepository(JournalRepositoryBase[_OperationJournalRecord]):
    """Synchronous atomic substrate specialized to persisted operation snapshots."""

    def __init__(self, *, storage_root: Path) -> None:
        super().__init__(
            journal_dirname=storage_location(StorageCategory.OPERATION_JOURNAL).subpath,
            storage_root=storage_root,
            parse_operation=_OperationJournalRecord.model_validate_json,
            error_type=RepositoryError,
            not_found_type=RepositoryError,
            corrupt_type=RepositoryError,
            subject="operation journal",
            id_subject="operation",
        )

    def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Atomically create or advance a snapshot after all transition checks pass."""
        self._validate_lease(snapshot, lease)
        self._ensure_root()
        path = self.path_for(snapshot.operation_id)
        with exclusive_file_lock(self.lock_target):
            if path.exists():
                current = super().load(snapshot.operation_id)
                self._validate_advance(current.snapshot, snapshot, expected_revision)
                record = _OperationJournalRecord(snapshot=snapshot, history=(*current.history, *snapshot.events))
            else:
                self._validate_create(snapshot, expected_revision)
                record = _OperationJournalRecord(snapshot=snapshot, history=snapshot.events)
            self._write(path, record)

    @staticmethod
    def _validate_lease(snapshot: OperationPersistedSnapshot, lease: OperationOwnerLease) -> None:
        if lease.operation_id != snapshot.operation_id:
            raise RepositoryError("operation lease does not match the persisted snapshot identity")

    @staticmethod
    def _validate_create(snapshot: OperationPersistedSnapshot, expected_revision: OperationRevision) -> None:
        if expected_revision != 0 or snapshot.revision != 0:
            raise RepositoryError(
                "initial operation journal create requires expected revision and snapshot revision zero"
            )
        if not snapshot.events and snapshot.event_cursor != 0:
            raise RepositoryError("initial operation journal create requires empty history cursor zero")
        if snapshot.events and snapshot.events[0].sequence != 1:
            raise RepositoryError("initial operation journal create event history must begin at sequence one")

    @staticmethod
    def _validate_advance(
        current: OperationPersistedSnapshot,
        snapshot: OperationPersistedSnapshot,
        expected_revision: OperationRevision,
    ) -> None:
        if expected_revision != current.revision:
            raise RepositoryError("operation journal compare-and-swap revision is stale")
        if snapshot.revision != current.revision + 1:
            raise RepositoryError("operation journal successor revision must advance exactly once")
        if snapshot.identity != current.identity:
            raise RepositoryError("operation journal transition cannot change operation identity")
        if snapshot.request_reference != current.request_reference:
            raise RepositoryError("operation journal transition cannot change the request reference")
        if snapshot.started_at != current.started_at:
            raise RepositoryError("operation journal transition cannot change the start time")
        if current.lifecycle.value == "terminal":
            raise RepositoryError("operation journal transition cannot advance a terminal operation")
        if not snapshot.events or snapshot.events[0].sequence != current.event_cursor + 1:
            raise RepositoryError("operation journal transition event cursor is not contiguous")


class OperationJournalRepository(OperationJournal, OperationEventStream):
    """Async operation-journal port over the atomic filesystem substrate."""

    def __init__(self, *, storage_root: Path) -> None:
        self._repository = _SnapshotJournalRepository(storage_root=storage_root)

    @override
    async def load(self, operation_id: str) -> OperationPersistedSnapshot:
        """Load the latest credential-free snapshot for one operation."""
        return self._repository.load(operation_id).snapshot

    @override
    async def read_after(
        self,
        operation_id: str,
        cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationReplayPage:
        """Return one bounded, exclusive page from retained event history."""
        request = _OperationReplayRequest(cursor=cursor, limit=limit)
        try:
            record = self._repository.load(operation_id)
        except RepositoryError:
            if self._is_absent(operation_id):
                return OperationReplayPage(
                    status=OperationReplayStatus.UNKNOWN_OPERATION,
                    requested_cursor=request.cursor,
                    events=(),
                    next_cursor=request.cursor,
                )
            raise
        events = tuple(event for event in record.history if event.sequence > request.cursor)[: request.limit]
        if not events:
            return OperationReplayPage(
                status=OperationReplayStatus.CAUGHT_UP,
                requested_cursor=request.cursor,
                events=(),
                next_cursor=request.cursor,
            )
        return OperationReplayPage(
            status=OperationReplayStatus.PAGE,
            requested_cursor=request.cursor,
            events=events,
            next_cursor=events[-1].sequence,
        )

    @override
    async def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Atomically create or advance the snapshot through the typed substrate."""
        self._repository.commit(snapshot, expected_revision=expected_revision, lease=lease)

    def _is_absent(self, operation_id: str) -> bool:
        """Distinguish an absent record from a present but unreadable record."""
        path = self._repository.path_for(operation_id)
        return not os.path.lexists(self._repository.root) or not os.path.lexists(path)


__all__ = ["OperationJournalRepository"]
