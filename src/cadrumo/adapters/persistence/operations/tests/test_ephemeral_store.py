"""The real supervisor runs an ephemeral operation wholly in memory, under the durable journal's rules."""

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
from cadrumo.application.operations.persistence.leases import OperationOwnerLease, operation_conflict_scope_reference
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
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
    OperationLifecycle,
    OperationTerminalCondition,
)

from ...storage.errors import RepositoryError
from ..ephemeral_store import EphemeralOperationStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_DEFINITION = "operation.synthetic.ephemeral-read"


class _Request(CredentialFreeOperationRequest):
    """A read that names nothing private."""

    page: int = 0


class _Result(BaseModel):
    """The page a read returns."""

    model_config = STRICT_FROZEN_CONFIG
    page: int


class _Reader:
    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.entered = asyncio.Event()

    async def execute(self, request: OperationRequest[_Request], context: OperationExecutorContext) -> str | None:
        self.entered.set()
        await self.release.wait()
        return await context.operands.put(_Result(page=request.payload.page), written_at=datetime.now(UTC))


def _registry(reader: _Reader) -> OperationRegistry:
    definition = OperationDefinition(
        definition_id=_DEFINITION,
        request_type=_Request,
        result_type=_Result,
        executor_factory=OperationExecutorFactory(request_type=_Request, executor_type=_Reader, build=lambda: reader),
        phase_codes=("operation.phase.synthetic",),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.EPHEMERAL,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.NONE,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        subject_reference=OperationSubjectReferenceV1.profile(),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{_DEFINITION}.request", schema_version=1, model_type=_Request
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{_DEFINITION}.result", schema_version=1, model_type=_Result
        ),
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _supervisor(store: EphemeralOperationStore, reader: _Reader) -> OperationSupervisor:
    return OperationSupervisor(
        registry=_registry(reader),
        authority_operation=unread_authority_operation(),
        journal=store,
        event_stream=store,
        leases=store,
        operands=store,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=1),
    )


def _request(page: int) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](definition_id=_DEFINITION, subject_ref="synthetic", payload=_Request(page=page))


@pytest.mark.asyncio
async def test_two_reads_of_one_subject_run_together_settle_and_keep_their_results_in_memory(tmp_path: Path) -> None:
    store, reader = EphemeralOperationStore(), _Reader()
    supervisor = _supervisor(store, reader)
    try:
        first = await supervisor.submit(_request(1))
        # A durable lease is one per definition and subject; an ephemeral one is the operation's own.
        second = await supervisor.submit(_request(2))
        await supervisor.start(first)
        await supervisor.start(second)
        await asyncio.wait_for(reader.entered.wait(), timeout=10)
        running = await store.read_observation(first, 0, limit=32)
        assert running.snapshot.lifecycle is OperationLifecycle.RUNNING
        reader.release.set()
        for operation_id, page in ((first, 1), (second, 2)):
            terminal = await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is OperationEffect.NONE
            receipt = terminal.terminal_receipt
            assert receipt is not None and receipt.result_ref is not None
            assert await store.resolve(receipt.result_ref, _Result) == _Result(page=page)
            replay = await store.read_after(operation_id, 0, limit=64)
            assert replay.status is OperationReplayStatus.PAGE
            assert replay.events[-1].sequence == terminal.event_cursor
        # Nothing of either read reached the filesystem.
        assert list(tmp_path.iterdir()) == []
    finally:
        reader.release.set()
        await supervisor.shutdown()


@pytest.mark.asyncio
async def test_an_operation_the_store_does_not_hold_reads_as_unknown() -> None:
    store = EphemeralOperationStore()
    with pytest.raises(OperationObservationUnknownOperationError):
        await store.read_observation("a" * 64, 0, limit=8)
    assert (await store.read_after("a" * 64, 0, limit=8)).status is OperationReplayStatus.UNKNOWN_OPERATION
    with pytest.raises(RepositoryError):
        await store.load("a" * 64)
    page = await store.inventory_page(after=None, limit=8)
    assert page.entries == () and not page.has_more


@pytest.mark.asyncio
async def test_settled_operations_beyond_the_retention_are_forgotten() -> None:
    store, reader = EphemeralOperationStore(settled_retention=1), _Reader()
    reader.release.set()
    supervisor = _supervisor(store, reader)
    try:
        settled = []
        for page in (1, 2):
            operation_id = await supervisor.submit(_request(page))
            await supervisor.start(operation_id)
            settled.append(await asyncio.wait_for(supervisor.settled(operation_id), timeout=10))
        older, newer = settled
        with pytest.raises(OperationObservationUnknownOperationError):
            await store.read_observation(older.identity.operation_id, 0, limit=8)
        assert (await store.read_observation(newer.identity.operation_id, 0, limit=8)).snapshot == newer
    finally:
        await supervisor.shutdown()


@pytest.mark.asyncio
async def test_a_commit_without_the_exact_live_lease_is_refused() -> None:
    store, reader = EphemeralOperationStore(), _Reader()
    supervisor = _supervisor(store, reader)
    try:
        operation_id = await supervisor.submit(_request(1))
        snapshot = await store.load(operation_id)
        now = datetime.now(UTC)
        stranger = OperationOwnerLease(
            operation_id=operation_id,
            scope_ref=operation_conflict_scope_reference(definition_id=_DEFINITION, subject_ref="synthetic"),
            owner_id="3" * 64,
            token="4" * 64,
            acquired_at=now - timedelta(seconds=1),
            expires_at=now + timedelta(minutes=1),
        )
        successor = snapshot.model_copy(update={"revision": 1, "updated_at": now})
        with pytest.raises(RepositoryError, match="exact current operation lease"):
            await store.commit(successor, expected_revision=0, lease=stranger)
    finally:
        await supervisor.shutdown()


@pytest.mark.asyncio
async def test_an_operations_own_operands_go_with_its_record() -> None:
    store, reader = EphemeralOperationStore(settled_retention=1), _Reader()
    reader.release.set()
    supervisor = _supervisor(store, reader)
    try:
        first = await supervisor.submit(_request(1))
        kept = await store.operands_for(first).put(_Result(page=1), written_at=datetime.now(UTC))
        assert await store.resolve(kept, _Result) == _Result(page=1)
        for operation_id in (first, await supervisor.submit(_request(2))):
            await supervisor.start(operation_id)
            await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
        assert not store.holds_operand(kept)
    finally:
        await supervisor.shutdown()
