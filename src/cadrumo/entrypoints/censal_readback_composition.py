"""Bind census readback to the existing journal and exact-profile encrypted custody."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from ..adapters.persistence.operations.journal import OperationJournalRepository
from ..adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.operations.persistence.journal import OperationSecureReferenceStore
from ..application.user_profile.censal_observation import CensalObservation
from ..application.user_profile.censal_readback import (
    CensalHistoryRead,
    read_censal_history,
    read_latest_censal_observation,
    refresh_censal_history,
)
from ..application.workbench_capture_memory import WorkbenchCensusMemo, WorkbenchCensusMemoKey
from ..core.paths import effective_storage_root


def _stored_journal() -> OperationJournalRepository:
    return OperationJournalRepository(storage_root=effective_storage_root())


def _profile_operands(profile_id: UUID) -> OperationSecureReferenceStore:
    return operation_secure_reference_repository(objects=secure_object_repository_for_bucket(str(profile_id)))


async def read_stored_censal_observation(profile_id: UUID) -> CensalObservation | None:
    """Read only this authenticated profile's durable census operation results."""
    return await read_latest_censal_observation(
        profile_id, journal=_stored_journal(), operands=_profile_operands(profile_id)
    )


@dataclass(frozen=True, slots=True)
class StoredCensalHistoryReader:
    """Read one profile's stored census, and recheck it from the journal records that could change it.

    With a ``memo`` a read starts from the classification the session's
    previous capture left, when one is kept for this exact profile and
    journal, and reads only the records that could have changed it; every
    read and recheck keeps its own up-to-date classification for the next.
    Without one, every read classifies the whole journal.
    """

    profile_id: UUID
    memo: WorkbenchCensusMemo | None = None

    def read(self) -> CensalHistoryRead:
        """Read the newest stored census observation and name the journal records it came from."""
        storage_root = effective_storage_root()
        key = WorkbenchCensusMemoKey(profile_id=self.profile_id, journal_root=str(storage_root))
        kept = None if self.memo is None else self.memo.recall(key)
        journal = OperationJournalRepository(storage_root=storage_root)
        operands = _profile_operands(self.profile_id)
        history = asyncio.run(
            read_censal_history(self.profile_id, journal=journal, operands=operands)
            if kept is None
            else refresh_censal_history(self.profile_id, kept, journal=journal, operands=operands)
        )
        self._keep(key, history)
        return history

    def recheck(self, prior: CensalHistoryRead) -> CensalObservation | None:
        """Answer the lookup again now, reading only census records and records created since ``prior``."""
        storage_root = effective_storage_root()
        history = asyncio.run(
            refresh_censal_history(
                self.profile_id,
                prior,
                journal=OperationJournalRepository(storage_root=storage_root),
                operands=_profile_operands(self.profile_id),
            )
        )
        self._keep(WorkbenchCensusMemoKey(profile_id=self.profile_id, journal_root=str(storage_root)), history)
        return history.observation

    def _keep(self, key: WorkbenchCensusMemoKey, history: CensalHistoryRead) -> None:
        if self.memo is not None:
            self.memo.keep(key, history)
