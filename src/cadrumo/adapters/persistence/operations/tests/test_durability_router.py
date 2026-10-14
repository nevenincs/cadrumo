"""Ephemeral operations stay in memory while recorded ones are journaled on disk, through one set of ports."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.application.operations.frontend_requests import (
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest, new_operation_id
from cadrumo.application.operations.observation import OperationObservationService
from cadrumo.application.operations.persistence.journal import OperationObservationUnknownOperationError
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.core.operations import (
    OperationTerminalCondition,
)

from ...storage.errors import RepositoryError
from .. import journal as journal_module
from .. import lease as lease_module
from ..durability_router import DurabilityRoutedOperationPersistence
from ..ephemeral_store import EphemeralOperationStore
from ..journal import OperationJournalRepository
from ..lease import OperationLeaseFilesystemRepository
from .routed_operation_support import (
    EPHEMERAL_DEFINITION_ID,
    RECORDED_DEFINITION_ID,
    SyntheticRequest,
    SyntheticResult,
    synthetic_routed_registry,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
async def test_only_the_recorded_operation_reaches_the_journal_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "synthetic-state"
    journal = OperationJournalRepository(storage_root=storage_root)
    # The durable operand store is not under test here; keeping it in memory leaves only journal rows on disk.
    persistence = DurabilityRoutedOperationPersistence(
        journal=journal,
        event_stream=journal,
        reader=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
        operands=EphemeralOperationStore(),
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
    try:
        settled = {}
        for definition_id in (EPHEMERAL_DEFINITION_ID, RECORDED_DEFINITION_ID):
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=definition_id, subject_ref="synthetic", payload=SyntheticRequest()
                )
            )
            await supervisor.start(operation_id)
            settled[definition_id] = await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
        for definition_id, terminal in settled.items():
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED, definition_id
            receipt = terminal.terminal_receipt
            assert receipt is not None and receipt.result_ref is not None
            assert await persistence.resolve(receipt.result_ref, SyntheticResult) == SyntheticResult(
                definition_id=definition_id
            )
            observed = await persistence.read_observation(terminal.identity.operation_id, 0, limit=64)
            assert observed.snapshot == terminal
        ephemeral_id = settled[EPHEMERAL_DEFINITION_ID].identity.operation_id
        recorded_id = settled[RECORDED_DEFINITION_ID].identity.operation_id
        rows = {path.name for path in storage_root.rglob("*.json")}
        assert f"{recorded_id}.json" in rows
        assert not any(ephemeral_id in name for name in rows), rows
        # The durable journal itself knows nothing of the ephemeral operation.
        with pytest.raises(OperationObservationUnknownOperationError):
            await journal.read_observation(ephemeral_id, 0, limit=8)
        assert persistence.routes_ephemeral(ephemeral_id)
        assert not persistence.routes_ephemeral(recorded_id)
    finally:
        await supervisor.shutdown()


def _router(storage_root: Path) -> DurabilityRoutedOperationPersistence:
    journal = OperationJournalRepository(storage_root=storage_root)
    return DurabilityRoutedOperationPersistence(
        journal=journal,
        event_stream=journal,
        reader=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
        operands=EphemeralOperationStore(),
    )


@pytest.mark.asyncio
async def test_frontends_read_an_ephemeral_result_and_after_its_process_ends_learn_it_is_unknown(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "synthetic-state"
    registry = synthetic_routed_registry()
    persistence = _router(storage_root)
    supervisor = OperationSupervisor(
        registry=registry,
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
    try:
        operation_id = await supervisor.submit(
            OperationRequest[BaseModel](
                definition_id=EPHEMERAL_DEFINITION_ID, subject_ref="synthetic", payload=SyntheticRequest()
            )
        )
        await supervisor.start(operation_id)
        terminal = await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
    finally:
        await supervisor.shutdown()
    contract = registry.lookup_public_contract(EPHEMERAL_DEFINITION_ID)
    assert contract.result_schema is not None
    observe = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32)
    result = OperationResultProjectionRequestV1(
        operation_id=operation_id,
        terminal_revision=terminal.revision,
        definition_contract_digest=contract.definition_contract_digest,
        result_schema=contract.result_schema,
    )

    observed = await OperationObservationService(reader=persistence, registry=registry).observe(observe)
    assert isinstance(observed, OperationObservationSuccessV1), observed
    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    released = await OperationResultProjectionService(
        reader=persistence, registry=registry, operands=persistence
    ).resolve(result, SyntheticResult)
    assert isinstance(released, OperationResultProjectionSuccessV1), released
    assert released.projection == SyntheticResult(definition_id=EPHEMERAL_DEFINITION_ID)

    # The worker ends: a fresh process starts over its durable journal, which never held the read.
    restarted = _router(storage_root)
    lost = await OperationObservationService(reader=restarted, registry=registry).observe(observe)
    assert (
        isinstance(lost, OperationObservationRefusalV1)
        and lost.code is OperationObservationRefusalCode.UNKNOWN_OPERATION
    )
    refused = await OperationResultProjectionService(reader=restarted, registry=registry, operands=restarted).resolve(
        result, SyntheticResult
    )
    assert isinstance(refused, OperationResultProjectionRefusalV1)
    assert refused.code is OperationResultProjectionRefusalCode.UNKNOWN_OPERATION


@pytest.mark.asyncio
async def test_an_ephemeral_read_takes_the_journal_lock_zero_times_and_a_recorded_one_still_takes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage_root = tmp_path / "synthetic-state"
    persistence = _router(storage_root)
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
    acquisitions: list[Path] = []
    real_lock = journal_module.exclusive_file_lock

    @contextmanager
    def counted_lock(target: Path) -> Generator[Path]:
        acquisitions.append(target)
        with real_lock(target) as held:
            yield held

    # Both durable adapters take the journal root's one lock through these module references.
    monkeypatch.setattr(journal_module, "exclusive_file_lock", counted_lock)
    monkeypatch.setattr(lease_module, "exclusive_file_lock", counted_lock)
    try:
        counts = {}
        for definition_id in (EPHEMERAL_DEFINITION_ID, RECORDED_DEFINITION_ID):
            before = len(acquisitions)
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=definition_id, subject_ref="synthetic", payload=SyntheticRequest()
                )
            )
            await supervisor.start(operation_id)
            await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
            await persistence.read_observation(operation_id, 0, limit=32)
            counts[definition_id] = len(acquisitions) - before
    finally:
        await supervisor.shutdown()
    assert counts[EPHEMERAL_DEFINITION_ID] == 0, counts
    assert counts[RECORDED_DEFINITION_ID] > 0, counts


@pytest.mark.asyncio
async def test_an_abandoned_admission_leaves_neither_routing_nor_operands(tmp_path: Path) -> None:
    persistence = _router(tmp_path / "synthetic-state")
    operation_id = new_operation_id()
    persistence.register_ephemeral(operation_id)
    reference = await persistence.operands_for(operation_id).put(
        SyntheticResult(definition_id=EPHEMERAL_DEFINITION_ID), written_at=datetime.now(UTC)
    )
    assert persistence.routes_ephemeral(operation_id)
    assert await persistence.resolve(reference, SyntheticResult) == SyntheticResult(
        definition_id=EPHEMERAL_DEFINITION_ID
    )

    persistence.abandon_ephemeral(operation_id)

    assert not persistence.routes_ephemeral(operation_id)
    # The durable operand store of this router is a separate in-memory store; it never held the operand.
    with pytest.raises(RepositoryError, match="absent"):
        await persistence.resolve(reference, SyntheticResult)
