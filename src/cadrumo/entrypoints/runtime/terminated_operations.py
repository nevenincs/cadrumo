"""Parent settlement for an already contained native profile worker."""

from __future__ import annotations

import time
from pathlib import Path

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...application.operations.persistence.journal import OperationRecoveryInventoryDisposition
from ...application.operations.registry import OperationRegistry
from ...application.operations.terminated_owner import settle_terminated_operation
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...core.time.clock import now


async def settle_terminated_worker_operations(
    *, root: Path, identity: ProfileWorkerIdentity, registry: OperationRegistry, deadline: float
) -> None:
    """Scan credential-free records only after native containment is confirmed.

    A corrupt or unreadable record leaves settlement incomplete. An expired
    matching lease stays with ordinary reconciliation. The caller retains this
    attempt until completion; a timed-out thread is never termination evidence.
    """
    journal = OperationJournalRepository(storage_root=root)
    leases = OperationLeaseFilesystemRepository(storage_root=root)
    cursor = None
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError("terminated worker settlement budget exhausted")
        page = await journal.inventory_page(after=cursor, limit=128)
        for entry in page.entries:
            if time.monotonic() >= deadline:
                raise TimeoutError("terminated worker settlement budget exhausted")
            if entry.disposition is OperationRecoveryInventoryDisposition.REFUSED:
                raise ValueError("terminated worker operation inventory is unreadable")
            await settle_terminated_operation(
                operation_id=entry.operation_id,
                terminated_owner_id=identity.operation_owner_id,
                journal=journal,
                leases=leases,
                registry=registry,
                observed_at=now(),
            )
        if not page.has_more:
            return
        cursor = page.next_cursor
