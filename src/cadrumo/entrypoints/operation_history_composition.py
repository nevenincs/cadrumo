"""Bind the operation history read to the shared journal and one profile's admission custody.

The journal belongs to the whole installation; the encrypted admission records
that say whose a run is live in each profile's own secure objects, opened
lazily for the exact bucket the read is bound to.

Core types: :class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`.
"""

from __future__ import annotations

from collections.abc import Awaitable
from functools import cache

from ..adapters.persistence.operations.journal import OperationJournalRepository
from ..adapters.persistence.operations.secure_references import OperationSecureReferenceRepository
from ..adapters.persistence.storage.errors import BlobNotFoundError, KeyringUnavailableError, RepositoryError
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..adapters.persistence.storage.secure_object_namespaces import OPERATION_SECURE_REFERENCE_NAMESPACE
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..application.operation_history.list_operation import OperationHistoryPorts
from ..application.operations.models import OperationId
from ..application.operations.persistence.journal import OperationPersistedSnapshot, OperationRecoveryInventoryDelta
from ..application.operations.provenance import OperationAdmissionProvenance
from ..application.persistence_errors import PersistenceDegradationError
from ..core.identity.digest import ContentDigest
from ..core.paths import effective_storage_root

_DATA_UNAVAILABLE = (RepositoryError, BlobNotFoundError, KeyringUnavailableError)
"""Failures that mean a record could not be read; every integrity failure keeps its own meaning and propagates."""


async def _degraded[T](operation: str, read: Awaitable[T]) -> T:
    try:
        return await read
    except _DATA_UNAVAILABLE as exc:
        raise PersistenceDegradationError(operation) from exc


def compose_operation_history_ports(bucket_id: str) -> OperationHistoryPorts:
    """Bind the journal and this exact profile's operand custody, opening the custody only when read."""
    journal = OperationJournalRepository(storage_root=effective_storage_root())

    @cache
    def objects() -> SecureObjectRepository:
        return secure_object_repository_for_bucket(bucket_id)

    operands = OperationSecureReferenceRepository(
        objects_factory=objects, namespace=OPERATION_SECURE_REFERENCE_NAMESPACE
    )

    async def inventory() -> OperationRecoveryInventoryDelta:
        return await _degraded("operations.history.inventory", journal.inventory_delta(known=frozenset()))

    async def load(operation_id: OperationId) -> OperationPersistedSnapshot:
        return await _degraded("operations.history.load", journal.load(operation_id))

    async def admission(reference: ContentDigest) -> OperationAdmissionProvenance | None:
        return await _degraded(
            "operations.history.admission", operands.resolve_if_held(reference, OperationAdmissionProvenance)
        )

    return OperationHistoryPorts(bucket_id=bucket_id, inventory=inventory, load=load, admission=admission)


__all__ = ["compose_operation_history_ports"]
