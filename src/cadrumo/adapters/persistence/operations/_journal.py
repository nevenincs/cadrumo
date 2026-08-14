"""Atomic filesystem implementation of the credential-free operation journal."""

from __future__ import annotations

import json
import os
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import cast, override

from pydantic import BaseModel, model_validator

from ....application.operations import (
    JournalRepositoryBase,
    OperationEvent,
    OperationEventCursor,
    OperationEventStream,
    OperationIdempotencyClaim,
    OperationJournal,
    OperationOwnerLease,
    OperationPersistedSnapshot,
    OperationReplayLimit,
    OperationReplayPage,
    OperationReplayStatus,
    OperationRevision,
    OperationTerminalEvent,
    operation_conflict_scope_reference,
)
from ....core import STRICT_FROZEN_CONFIG, StorageCategory, exclusive_file_lock, storage_location
from ..storage import RepositoryError
from ._lease import OperationLeaseStorage


def _raise_if(condition: bool, message: str, error_type: type[Exception]) -> None:
    if condition:
        raise error_type(message)


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


def _parse_operation_journal_record(raw: str | bytes) -> _OperationJournalRecord:
    """Migrate the credential-free v1 snapshot before any lease decision."""
    document = cast(dict[str, object], json.loads(raw))
    snapshot = document.get("snapshot")
    if isinstance(snapshot, dict):
        snapshot_document = cast(dict[str, object], snapshot)
        if snapshot_document.get("schema_version") == 1:
            snapshot_document["schema_version"] = 2
            snapshot_document.setdefault("idempotency_claim", None)
            snapshot_document.setdefault("pending_interaction", None)
            snapshot_document.setdefault("consumed_interactions", [])
    return _OperationJournalRecord.model_validate_json(json.dumps(document))


class _SnapshotJournalRepository(JournalRepositoryBase[_OperationJournalRecord]):
    """Synchronous atomic substrate specialized to persisted operation snapshots."""

    def __init__(self, *, storage_root: Path) -> None:
        super().__init__(
            journal_dirname=storage_location(StorageCategory.OPERATION_JOURNAL).subpath,
            storage_root=storage_root,
            parse_operation=_parse_operation_journal_record,
            error_type=RepositoryError,
            not_found_type=RepositoryError,
            corrupt_type=RepositoryError,
            subject="operation journal",
            id_subject="operation",
        )
        self._lease_storage = OperationLeaseStorage(storage_root=storage_root)

    def resolve_idempotency(self, claim: OperationIdempotencyClaim) -> str | None:
        """Resolve a durable retry key from a complete operation journal only."""
        self._ensure_root()
        with exclusive_file_lock(self.lock_target):
            return self._resolve_idempotency_unlocked(claim)

    def _resolve_idempotency_unlocked(self, claim: OperationIdempotencyClaim) -> str | None:
        """Find one exact claim while the canonical journal lock is already held."""
        matched_operation_id: str | None = None
        for path in self.root.glob("*.json"):
            operation_id = path.stem
            if len(operation_id) != 64 or any(character not in "0123456789abcdef" for character in operation_id):
                continue
            persisted_claim = super().load(operation_id).snapshot.idempotency_claim
            if persisted_claim is None or persisted_claim.key_digest != claim.key_digest:
                continue
            if (
                persisted_claim.definition_id,
                persisted_claim.subject_ref,
                persisted_claim.key_digest,
                persisted_claim.request_reference,
            ) != (
                claim.definition_id,
                claim.subject_ref,
                claim.key_digest,
                claim.request_reference,
            ):
                raise RepositoryError("operation idempotency key is bound to a different request")
            if matched_operation_id is not None and matched_operation_id != persisted_claim.operation_id:
                raise RepositoryError("operation idempotency key is bound to multiple operations")
            matched_operation_id = persisted_claim.operation_id
        return matched_operation_id

    def create(self, snapshot: OperationPersistedSnapshot, *, lease: OperationOwnerLease) -> str:
        """Create the initial snapshot and its retry claim in one journal write."""
        self._validate_lease(snapshot, lease)
        self._ensure_root()
        path = self.path_for(snapshot.operation_id)
        with exclusive_file_lock(self.lock_target):
            self._lease_storage.require_live_exact_unlocked(
                scope_ref=lease.scope_ref,
                operation_id=snapshot.operation_id,
                lease=lease,
                observed_at=snapshot.updated_at,
            )
            if snapshot.idempotency_claim is not None:
                existing = self._resolve_idempotency_unlocked(snapshot.idempotency_claim)
                if existing is not None:
                    return existing
            if os.path.lexists(path):
                raise RepositoryError("initial operation journal create already exists")
            self._validate_create(snapshot, expected_revision=0)
            self._write(path, _OperationJournalRecord(snapshot=snapshot, history=snapshot.events))
        return snapshot.operation_id

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
            self._lease_storage.require_live_exact_unlocked(
                scope_ref=lease.scope_ref,
                operation_id=snapshot.operation_id,
                lease=lease,
                observed_at=snapshot.updated_at,
            )
            if path.exists():
                current = super().load(snapshot.operation_id)
                self._validate_advance(current.snapshot, snapshot, expected_revision)
                record = _OperationJournalRecord(snapshot=snapshot, history=(*current.history, *snapshot.events))
            else:
                if snapshot.idempotency_claim is not None:
                    raise RepositoryError("idempotent operation creation requires the journal create protocol")
                self._validate_create(snapshot, expected_revision)
                record = _OperationJournalRecord(snapshot=snapshot, history=snapshot.events)
            self._write(path, record)

    @staticmethod
    def _validate_lease(snapshot: OperationPersistedSnapshot, lease: OperationOwnerLease) -> None:
        if lease.operation_id != snapshot.operation_id:
            raise RepositoryError("operation lease does not match the persisted snapshot identity")
        expected_scope_ref = operation_conflict_scope_reference(
            definition_id=snapshot.identity.definition_id,
            subject_ref=snapshot.identity.subject_ref,
        )
        if lease.scope_ref != expected_scope_ref:
            raise RepositoryError("operation lease does not match the persisted snapshot conflict scope")

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
        snapshot.request_reference != current.request_reference,
        "operation journal transition cannot change the request reference",
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


class OperationJournalRepository(OperationJournal, OperationEventStream):
    """Async operation-journal port over the atomic filesystem substrate."""

    def __init__(self, *, storage_root: Path) -> None:
        self._repository = _SnapshotJournalRepository(storage_root=storage_root)

    @override
    async def load(self, operation_id: str) -> OperationPersistedSnapshot:
        """Load the latest credential-free snapshot for one operation."""
        return self._repository.load(operation_id).snapshot

    @override
    async def resolve_idempotency(self, claim: OperationIdempotencyClaim) -> str | None:
        return self._repository.resolve_idempotency(claim)

    @override
    async def create(self, snapshot: OperationPersistedSnapshot, *, lease: OperationOwnerLease) -> str:
        """Create a complete initial journal before making an idempotency replay visible."""
        return self._repository.create(snapshot, lease=lease)

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
