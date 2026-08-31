"""Atomic filesystem implementation of the credential-free operation journal."""

from __future__ import annotations

import os
from pathlib import Path
from typing import override

from pydantic import BaseModel

from ....application.journal_repository import JournalRepositoryBase
from ....application.operations.event_replay import OperationEventCursor
from ....application.operations.models import OperationRevision
from ....application.operations.persistence.idempotency import OperationIdempotencyClaim
from ....application.operations.persistence.journal import (
    OperationEventStream,
    OperationJournal,
    OperationObservationCursorAheadError,
    OperationObservationMaterialization,
    OperationObservationReader,
    OperationObservationUnknownOperationError,
    OperationPersistedSnapshot,
    OperationProgressFoldInput,
)
from ....application.operations.persistence.leases import (
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from ....application.operations.persistence.replay import (
    OperationReplayLimit,
    OperationReplayPage,
    OperationReplayStatus,
)
from ....core.storage_taxonomy_locations import storage_location
from ....core.storage_taxonomy import StorageCategory
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.locks import exclusive_file_lock
from ....core.directory_scan import (
    scan_directory,
)
from ....core.locks import exclusive_file_lock_async
from ..storage import RepositoryError
from ._journal_validation import OperationJournalRecord, validate_advance
from .lease import OperationLeaseStorage


class _OperationReplayRequest(BaseModel):
    """Strict adapter-local replay inputs before filesystem access."""

    model_config = STRICT_FROZEN_CONFIG

    cursor: OperationEventCursor
    limit: OperationReplayLimit


def _replay_page_from_record(
    record: OperationJournalRecord,
    request: _OperationReplayRequest,
) -> OperationReplayPage:
    """Build one bounded replay page from the exact record already read."""
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


def _observation_materialization_from_record(
    record: OperationJournalRecord,
    request: _OperationReplayRequest,
) -> OperationObservationMaterialization:
    """Derive every observation fact from one immutable journal record."""
    anchor_cursor = record.snapshot.event_cursor
    if request.cursor > anchor_cursor:
        raise OperationObservationCursorAheadError(
            requested_cursor=request.cursor,
            anchor_cursor=anchor_cursor,
        )
    return OperationObservationMaterialization(
        snapshot=record.snapshot,
        anchor_cursor=anchor_cursor,
        replay=_replay_page_from_record(record, request),
        progress_fold=OperationProgressFoldInput(events=record.history),
    )


class _SnapshotJournalRepository(JournalRepositoryBase[OperationJournalRecord]):
    """Synchronous atomic substrate specialized to persisted operation snapshots."""

    def __init__(self, *, storage_root: Path) -> None:
        super().__init__(
            journal_dirname=storage_location(StorageCategory.OPERATION_JOURNAL).subpath,
            storage_root=storage_root,
            parse_operation=OperationJournalRecord.model_validate_json,
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

    def read_observation(
        self,
        operation_id: str,
        request: _OperationReplayRequest,
    ) -> OperationObservationMaterialization | None:
        """Read one complete record and its observation under the journal lock."""
        if not self._validate_existing_root():
            return None
        with exclusive_file_lock(self.lock_target):
            return self._read_observation_unlocked(operation_id, request)

    def read_observation_root_present(self) -> bool:
        """Tell whether the journal root exists, without taking the lock."""
        return self._validate_existing_root()

    def _read_observation_unlocked(
        self,
        operation_id: str,
        request: _OperationReplayRequest,
    ) -> OperationObservationMaterialization | None:
        """Read one record and its observation with the journal lock already held.

        Split out so an awaitable caller can hold the same lock through
        :func:`exclusive_file_lock_async` instead of blocking its event
        loop inside the synchronous acquisition.
        """
        try:
            record = super().load(operation_id)
        except RepositoryError:
            if self._is_absent(operation_id):
                return None
            raise
        return _observation_materialization_from_record(record, request)

    def _is_absent(self, operation_id: str) -> bool:
        """Tell a missing record from a present but unreadable one."""
        path = self.path_for(operation_id)
        return not os.path.lexists(self.root) or not os.path.lexists(path)

    def _resolve_idempotency_unlocked(self, claim: OperationIdempotencyClaim) -> str | None:
        """Find one exact claim while the canonical journal lock is already held."""
        matched_operation_id: str | None = None
        for path in scan_directory(self.root, pattern="*.json"):
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
            self._write(path, OperationJournalRecord(snapshot=snapshot, history=snapshot.events))
        return snapshot.operation_id

    def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Atomically advance an existing snapshot after all transition checks pass."""
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
            if not os.path.lexists(path):
                raise RepositoryError("operation journal commit requires an existing snapshot created via create")
            current = super().load(snapshot.operation_id)
            self._validate_advance(current.snapshot, snapshot, expected_revision)
            record = OperationJournalRecord(snapshot=snapshot, history=(*current.history, *snapshot.events))
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
        validate_advance(current, snapshot, expected_revision)


class OperationJournalRepository(OperationJournal, OperationEventStream, OperationObservationReader):
    """Async operation-journal port over the atomic filesystem substrate."""

    def __init__(self, *, storage_root: Path) -> None:
        """Bind the repository to the configured secure storage root."""
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
        return _replay_page_from_record(record, request)

    @override
    async def read_observation(
        self,
        operation_id: str,
        after_cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationObservationMaterialization:
        """Return snapshot, replay, and progress facts anchored to one locked record.

        The lock is acquired through the awaitable twin because the sole
        caller is a UI poll worker on the interface event loop: the
        synchronous acquisition parks that loop in ``time.sleep`` for the
        whole contention window, stalling every other task on it, and
        cannot be cancelled when the operator closes the surface.
        """
        if not self._repository.read_observation_root_present():
            raise OperationObservationUnknownOperationError(operation_id)
        async with exclusive_file_lock_async(self._repository.lock_target):
            materialization = self._repository._read_observation_unlocked(
                operation_id,
                _OperationReplayRequest(cursor=after_cursor, limit=limit),
            )
        if materialization is None:
            raise OperationObservationUnknownOperationError(operation_id)
        return materialization

    @override
    async def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Atomically advance an existing snapshot through the typed substrate."""
        self._repository.commit(snapshot, expected_revision=expected_revision, lease=lease)

    def _is_absent(self, operation_id: str) -> bool:
        """Distinguish an absent record from a present but unreadable record."""
        return self._repository._is_absent(operation_id)


__all__ = ["OperationJournalRepository"]
