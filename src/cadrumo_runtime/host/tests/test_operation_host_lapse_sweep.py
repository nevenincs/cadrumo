"""The worker host's lapsed-owner sweep never reaches the journal for an ephemeral read."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations import journal as journal_module
from cadrumo.adapters.persistence.operations import lease as lease_module
from cadrumo.adapters.persistence.operations.durability_router import DurabilityRoutedOperationPersistence
from cadrumo.adapters.persistence.operations.ephemeral_store import EphemeralOperationStore
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.tests.routed_operation_support import (
    EPHEMERAL_DEFINITION_ID,
    RECORDED_DEFINITION_ID,
    SyntheticRequest,
    synthetic_routed_registry,
)
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.composition import OperationComposedServices
from cadrumo.application.operations.models import OperationId, OperationRequest
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation

from ...adapters.worker_authorization_client import WorkerAuthorizationClient
from ..operation_host import ProfileWorkerOperationHost

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_the_lapse_sweep_takes_the_journal_lock_only_for_a_recorded_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage_root = tmp_path / "synthetic-state"
    journal = OperationJournalRepository(storage_root=storage_root)
    # One settled read is kept, so the second read forgets the first, as a busy worker's reads do.
    persistence = DurabilityRoutedOperationPersistence(
        journal=journal,
        event_stream=journal,
        reader=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
        operands=EphemeralOperationStore(),
        ephemeral=EphemeralOperationStore(settled_retention=1),
    )
    supervisor = OperationSupervisor(
        registry=synthetic_routed_registry(),
        authority_operation=unread_authority_operation(),
        journal=persistence,
        event_stream=persistence,
        leases=persistence,
        operands=persistence,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=1),
        ephemeral=persistence,
    )
    # Only the services container is stood in; the supervisor, router and stores are real.
    host = ProfileWorkerOperationHost(
        cast(ProfileWorkerCustody, object()), authorization=cast(WorkerAuthorizationClient, object())
    )
    host._services = cast(
        OperationComposedServices, cast(object, SimpleNamespace(submission=SimpleNamespace(supervisor=supervisor)))
    )
    acquisitions: list[Path] = []
    real_lock = journal_module.exclusive_file_lock

    @contextmanager
    def counted_lock(target: Path) -> Generator[Path]:
        acquisitions.append(target)
        with real_lock(target) as held:
            yield held

    async def admitted(definition_id: str) -> OperationId:
        operation_id = await supervisor.submit(
            OperationRequest[BaseModel](
                definition_id=definition_id, subject_ref="synthetic", payload=SyntheticRequest()
            )
        )
        host._track_unsettled(operation_id, definition_id)
        await supervisor.start(operation_id)
        await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
        return operation_id

    try:
        forgotten = await admitted(EPHEMERAL_DEFINITION_ID)
        await admitted(EPHEMERAL_DEFINITION_ID)
        assert not persistence.routes_ephemeral(forgotten)
        monkeypatch.setattr(journal_module, "exclusive_file_lock", counted_lock)
        monkeypatch.setattr(lease_module, "exclusive_file_lock", counted_lock)
        await host._settle_lapsed_operations()
        assert acquisitions == []

        # Positive control: a recorded operation is swept, through the journal, and then dropped.
        monkeypatch.undo()
        recorded = await admitted(RECORDED_DEFINITION_ID)
        assert host._unsettled == {recorded}
        monkeypatch.setattr(journal_module, "exclusive_file_lock", counted_lock)
        monkeypatch.setattr(lease_module, "exclusive_file_lock", counted_lock)
        host._lapse_checked_at = None
        await host._settle_lapsed_operations()
        assert acquisitions
        assert host._unsettled == set()
    finally:
        await supervisor.shutdown()
