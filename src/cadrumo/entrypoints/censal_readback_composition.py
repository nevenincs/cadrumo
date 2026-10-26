"""Bind census readback to the existing journal and exact-profile encrypted custody."""

from __future__ import annotations

from uuid import UUID

from ..adapters.persistence.operations.journal import OperationJournalRepository
from ..adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.user_profile.censal_observation import CensalObservation
from ..application.user_profile.censal_readback import read_latest_censal_observation
from ..core.paths import effective_storage_root


async def read_stored_censal_observation(profile_id: UUID) -> CensalObservation | None:
    """Read only this authenticated profile's durable census operation results."""
    return await read_latest_censal_observation(
        profile_id,
        journal=OperationJournalRepository(storage_root=effective_storage_root()),
        operands=operation_secure_reference_repository(objects=secure_object_repository_for_bucket(str(profile_id))),
    )
