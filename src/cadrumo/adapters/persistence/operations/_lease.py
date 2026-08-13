"""Durable filesystem owner leases for supervised operations."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal, override

from pydantic import BaseModel, model_validator

from ....application.operations import (
    JournalRepositoryBase,
    OperationId,
    OperationLeaseDisposition,
    OperationLeaseObservation,
    OperationLeaseObservationDisposition,
    OperationLeaseRepository,
    OperationLeaseResult,
    OperationOwnerLease,
)
from ....core import STRICT_FROZEN_CONFIG, StorageCategory, exclusive_file_lock, storage_location
from ....core.time import validate_utc_aware
from ..storage import RepositoryError


class _OperationLeaseRecord(BaseModel):
    """One versioned credential-free durable lease state."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = 1
    operation_id: OperationId
    recorded_at: datetime
    lease: OperationOwnerLease | None

    @model_validator(mode="after")
    def _validate_record(self) -> _OperationLeaseRecord:
        validate_utc_aware(self.recorded_at)
        if self.lease is not None:
            if self.lease.operation_id != self.operation_id:
                raise ValueError("durable operation lease record identity does not match its lease")
            if self.lease.acquired_at > self.recorded_at:
                raise ValueError("durable operation lease record precedes lease acquisition")
        return self

    @property
    def started_at(self) -> datetime:
        """Provide the ordering field required by the journal substrate."""
        return self.recorded_at


class OperationLeaseStorage(JournalRepositoryBase[_OperationLeaseRecord]):
    """Shared operation-journal-root lease storage and lock authority.

    The journal adapter uses the non-locking current-lease read only while it
    already holds this same repository lock.  Lease transitions acquire that
    lock here, preventing a nested acquisition around journal commits.
    """

    def __init__(self, *, storage_root: Path) -> None:
        super().__init__(
            journal_dirname=storage_location(StorageCategory.OPERATION_JOURNAL).subpath,
            storage_root=storage_root,
            parse_operation=_OperationLeaseRecord.model_validate_json,
            error_type=RepositoryError,
            not_found_type=RepositoryError,
            corrupt_type=RepositoryError,
            subject="operation lease",
            id_subject="operation",
        )

    @override
    def path_for(self, operation_id: str) -> Path:
        """Keep lease records beside, but distinct from, snapshot journals."""
        return super().path_for(operation_id).with_suffix(".lease.json")

    def ensure_root(self) -> None:
        """Materialize the canonical secure journal root before locking it."""
        self._ensure_root()

    def current_unlocked(self, operation_id: OperationId) -> OperationOwnerLease | None:
        """Load the exact lease state while the caller owns :attr:`lock_target`."""
        path = self.path_for(operation_id)
        if not os.path.lexists(path):
            return None
        return super().load(operation_id).lease

    def replace_unlocked(
        self,
        operation_id: OperationId,
        lease: OperationOwnerLease | None,
        *,
        observed_at: datetime,
    ) -> None:
        """Atomically replace one lease state while the caller owns the lock."""
        record = _OperationLeaseRecord(operation_id=operation_id, recorded_at=observed_at, lease=lease)
        self._write(self.path_for(operation_id), record)

    def require_live_exact_unlocked(self, lease: OperationOwnerLease, *, observed_at: datetime) -> None:
        """Refuse a journal writer without the exact active durable lease."""
        validate_utc_aware(observed_at)
        current = self.current_unlocked(lease.operation_id)
        if current is None:
            raise RepositoryError("operation journal commit requires a current durable operation lease")
        if current != lease:
            raise RepositoryError("operation journal commit lease is not the exact current durable operation lease")
        if current.acquired_at > observed_at:
            raise RepositoryError("operation journal commit lease is not yet active at the supplied evidence time")
        if current.expires_at <= observed_at:
            raise RepositoryError("operation journal commit lease is expired at the supplied evidence time")


class OperationLeaseFilesystemRepository(OperationLeaseRepository):
    """Caller-clocked durable owner-lease port over the operation journal root."""

    def __init__(self, *, storage_root: Path) -> None:
        self._storage = OperationLeaseStorage(storage_root=storage_root)

    @override
    async def inspect(self, operation_id: OperationId, *, observed_at: datetime) -> OperationLeaseObservation:
        """Return absent, active, or expired durable lease state at ``observed_at``."""
        self._storage.ensure_root()
        with exclusive_file_lock(self._storage.lock_target):
            current = self._storage.current_unlocked(operation_id)
            if current is None:
                return OperationLeaseObservation(
                    operation_id=operation_id,
                    disposition=OperationLeaseObservationDisposition.ABSENT,
                    observed_at=observed_at,
                )
            disposition = (
                OperationLeaseObservationDisposition.ACTIVE
                if current.expires_at > observed_at
                else OperationLeaseObservationDisposition.EXPIRED
            )
            return OperationLeaseObservation(
                operation_id=operation_id,
                disposition=disposition,
                observed_at=observed_at,
                current=current,
            )

    @override
    async def acquire(self, candidate: OperationOwnerLease, *, observed_at: datetime) -> OperationLeaseResult:
        """Acquire only an absent lease; live and expired predecessors remain unchanged."""
        self._storage.ensure_root()
        with exclusive_file_lock(self._storage.lock_target):
            current = self._storage.current_unlocked(candidate.operation_id)
            if current is None:
                result = OperationLeaseResult(
                    operation_id=candidate.operation_id,
                    disposition=OperationLeaseDisposition.ACQUIRED,
                    observed_at=observed_at,
                    current=candidate,
                )
                self._storage.replace_unlocked(candidate.operation_id, candidate, observed_at=observed_at)
                return result
            if current.expires_at > observed_at:
                return OperationLeaseResult(
                    operation_id=candidate.operation_id,
                    disposition=OperationLeaseDisposition.CONFLICT,
                    observed_at=observed_at,
                    current=current,
                )
            return OperationLeaseResult(
                operation_id=candidate.operation_id,
                disposition=OperationLeaseDisposition.EXPIRED,
                observed_at=observed_at,
                predecessor=current,
            )

    @override
    async def compare_and_swap(
        self,
        predecessor: OperationOwnerLease,
        successor: OperationOwnerLease,
        *,
        observed_at: datetime,
    ) -> OperationLeaseResult:
        """Renew an exact live owner or take over an exact expired owner."""
        self._storage.ensure_root()
        with exclusive_file_lock(self._storage.lock_target):
            current = self._storage.current_unlocked(predecessor.operation_id)
            if current != predecessor:
                return OperationLeaseResult(
                    operation_id=predecessor.operation_id,
                    disposition=OperationLeaseDisposition.OWNER_LOST,
                    observed_at=observed_at,
                    predecessor=predecessor,
                    current=current,
                )
            assert current is not None
            disposition = (
                OperationLeaseDisposition.RENEWED
                if current.expires_at > observed_at
                else OperationLeaseDisposition.TAKEN_OVER
            )
            result = OperationLeaseResult(
                operation_id=predecessor.operation_id,
                disposition=disposition,
                observed_at=observed_at,
                predecessor=predecessor,
                current=successor,
            )
            self._storage.replace_unlocked(predecessor.operation_id, successor, observed_at=observed_at)
            return result

    @override
    async def release(self, predecessor: OperationOwnerLease, *, observed_at: datetime) -> OperationLeaseResult:
        """Release only the exact current lease and persist its absent successor."""
        self._storage.ensure_root()
        with exclusive_file_lock(self._storage.lock_target):
            current = self._storage.current_unlocked(predecessor.operation_id)
            if current != predecessor:
                return OperationLeaseResult(
                    operation_id=predecessor.operation_id,
                    disposition=OperationLeaseDisposition.OWNER_LOST,
                    observed_at=observed_at,
                    predecessor=predecessor,
                    current=current,
                )
            result = OperationLeaseResult(
                operation_id=predecessor.operation_id,
                disposition=OperationLeaseDisposition.RELEASED,
                observed_at=observed_at,
                predecessor=predecessor,
            )
            self._storage.replace_unlocked(predecessor.operation_id, None, observed_at=observed_at)
            return result


__all__ = ["OperationLeaseFilesystemRepository", "OperationLeaseStorage"]
