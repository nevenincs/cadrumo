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
    recheck_censal_history,
)
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
    """Read one profile's stored census once, and recheck it from the journal records that could change it."""

    profile_id: UUID

    def read(self) -> CensalHistoryRead:
        """Read the newest stored census observation and name the journal records it came from."""
        return asyncio.run(
            read_censal_history(self.profile_id, journal=_stored_journal(), operands=_profile_operands(self.profile_id))
        )

    def recheck(self, prior: CensalHistoryRead) -> CensalObservation | None:
        """Answer the lookup again now, reading only census records and records created since ``prior``."""
        return asyncio.run(
            recheck_censal_history(
                self.profile_id, prior, journal=_stored_journal(), operands=_profile_operands(self.profile_id)
            )
        )
