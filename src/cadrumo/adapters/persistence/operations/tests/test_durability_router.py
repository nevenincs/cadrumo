"""Ephemeral operations stay in memory while recorded ones are journaled on disk, through one set of ports."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
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
from cadrumo.application.operations.models import CredentialFreeOperationRequest, OperationRequest, new_operation_id
from cadrumo.application.operations.observation import OperationObservationService
from cadrumo.application.operations.operation_definition import OperationDefinition, OperationExecutorFactory
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationObservationUnknownOperationError
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.application.operations.subject_reference import OperationSubjectReferenceV1
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
)

from ...storage.errors import RepositoryError
from .. import journal as journal_module
from .. import lease as lease_module
from ..durability_router import DurabilityRoutedOperationPersistence
from ..ephemeral_store import EphemeralOperationStore
from ..journal import OperationJournalRepository
from ..lease import OperationLeaseFilesystemRepository

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_EPHEMERAL = "operation.synthetic.routed-read"
_RECORDED = "operation.synthetic.routed-record"


class _Request(CredentialFreeOperationRequest):
    """A request that names nothing private."""


class _Result(BaseModel):
    """What either operation returns."""

    model_config = STRICT_FROZEN_CONFIG
    definition_id: str


class _Executor:
    async def execute(self, request: OperationRequest[_Request], context: OperationExecutorContext) -> str | None:
        return await context.operands.put(_Result(definition_id=request.definition_id), written_at=datetime.now(UTC))


def _definition(definition_id: str, *, ephemeral: bool) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=_Request,
        result_type=_Result,
        executor_factory=OperationExecutorFactory(request_type=_Request, executor_type=_Executor, build=_Executor),
        phase_codes=("operation.phase.synthetic",),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.EPHEMERAL if ephemeral else OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.NONE if ephemeral else OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE})
            if ephemeral
            else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        subject_reference=OperationSubjectReferenceV1.profile(),
    )


def _registry() -> OperationRegistry:
    definitions = (_definition(_EPHEMERAL, ephemeral=True), _definition(_RECORDED, ephemeral=False))
    registrations = tuple(
        OperationPublicDefinitionRegistrationV1.compose(
            definition=definition,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=f"{definition.definition_id}.request", schema_version=1, model_type=_Request
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=f"{definition.definition_id}.result", schema_version=1, model_type=_Result
            ),
        )
        for definition in definitions
    )
    return OperationRegistry(definitions=definitions, public_registrations=registrations)


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
        registry=_registry(),
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
        for definition_id in (_EPHEMERAL, _RECORDED):
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](definition_id=definition_id, subject_ref="synthetic", payload=_Request())
            )
            await supervisor.start(operation_id)
            settled[definition_id] = await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
        for definition_id, terminal in settled.items():
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED, definition_id
            receipt = terminal.terminal_receipt
            assert receipt is not None and receipt.result_ref is not None
            assert await persistence.resolve(receipt.result_ref, _Result) == _Result(definition_id=definition_id)
            observed = await persistence.read_observation(terminal.identity.operation_id, 0, limit=64)
            assert observed.snapshot == terminal
        ephemeral_id = settled[_EPHEMERAL].identity.operation_id
        recorded_id = settled[_RECORDED].identity.operation_id
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
    registry = _registry()
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
            OperationRequest[BaseModel](definition_id=_EPHEMERAL, subject_ref="synthetic", payload=_Request())
        )
        await supervisor.start(operation_id)
        terminal = await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
    finally:
        await supervisor.shutdown()
    contract = registry.lookup_public_contract(_EPHEMERAL)
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
    ).resolve(result, _Result)
    assert isinstance(released, OperationResultProjectionSuccessV1), released
    assert released.projection == _Result(definition_id=_EPHEMERAL)

    # The worker ends: a fresh process starts over its durable journal, which never held the read.
    restarted = _router(storage_root)
    lost = await OperationObservationService(reader=restarted, registry=registry).observe(observe)
    assert (
        isinstance(lost, OperationObservationRefusalV1)
        and lost.code is OperationObservationRefusalCode.UNKNOWN_OPERATION
    )
    refused = await OperationResultProjectionService(reader=restarted, registry=registry, operands=restarted).resolve(
        result, _Result
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
        registry=_registry(),
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
        for definition_id in (_EPHEMERAL, _RECORDED):
            before = len(acquisitions)
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](definition_id=definition_id, subject_ref="synthetic", payload=_Request())
            )
            await supervisor.start(operation_id)
            await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
            await persistence.read_observation(operation_id, 0, limit=32)
            counts[definition_id] = len(acquisitions) - before
    finally:
        await supervisor.shutdown()
    assert counts[_EPHEMERAL] == 0, counts
    assert counts[_RECORDED] > 0, counts


@pytest.mark.asyncio
async def test_an_abandoned_admission_leaves_neither_routing_nor_operands(tmp_path: Path) -> None:
    persistence = _router(tmp_path / "synthetic-state")
    operation_id = new_operation_id()
    persistence.register_ephemeral(operation_id)
    reference = await persistence.operands_for(operation_id).put(
        _Result(definition_id=_EPHEMERAL), written_at=datetime.now(UTC)
    )
    assert persistence.routes_ephemeral(operation_id)
    assert await persistence.resolve(reference, _Result) == _Result(definition_id=_EPHEMERAL)

    persistence.abandon_ephemeral(operation_id)

    assert not persistence.routes_ephemeral(operation_id)
    # The durable operand store of this router is a separate in-memory store; it never held the operand.
    with pytest.raises(RepositoryError, match="absent"):
        await persistence.resolve(reference, _Result)
