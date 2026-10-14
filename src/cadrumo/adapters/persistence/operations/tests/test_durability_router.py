"""Ephemeral operations stay in memory while recorded ones are journaled on disk, through one set of ports."""

from __future__ import annotations

import asyncio
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
from cadrumo.application.operations.models import CredentialFreeOperationRequest, OperationRequest
from cadrumo.application.operations.operation_definition import OperationDefinition, OperationExecutorFactory
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationObservationUnknownOperationError
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
