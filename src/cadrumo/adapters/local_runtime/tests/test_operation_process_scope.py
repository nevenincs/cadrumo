"""Native Job cleanup through the existing supervisor and durable operation stores."""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.models import CredentialFreeOperationRequest, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.leases import (
    OperationLeaseObservationDisposition,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
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

from ..windows_process import WindowsProcessScope
from .process_support import fixture_arguments, fixture_environment, native_python

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows Job cleanup"),
]

_DEFINITION = "operation.synthetic.process"


class _Request(CredentialFreeOperationRequest):
    """No private operands are required for the synthetic process operation."""


class _Result(BaseModel):
    """Empty synthetic result projection for the registered test executor."""

    model_config = STRICT_FROZEN_CONFIG


class _ProcessExecutor:
    def __init__(self, root: Path, *, cancel: bool) -> None:
        self.root, self.cancel = root, cancel
        self.ready = asyncio.Event()
        self.release = asyncio.Event()
        self.scope: WindowsProcessScope | None = None

    def cleanup_fixture(self) -> None:
        if self.scope is not None:
            self.scope.terminate()

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str | None:
        del request
        scope = WindowsProcessScope()
        try:
            # Ownership precedes launch, and the existing supervisor chooses
            # when resource cleanup is complete enough for terminal settlement.
            context.cleanup.own(scope, family=OperationOwnedResource.PROCESS)
        except BaseException:
            scope.terminate()
            raise
        self.scope = scope
        record = self.root / "process-facts.json"
        scope.launch(
            executable=native_python(),
            arguments=fixture_arguments("cadrumo.adapters.local_runtime.tests.job_fixture", "tree", str(record)),
            directory=self.root,
            environment=fixture_environment(),
        )
        deadline = time.monotonic() + 5
        while not record.is_file():
            if time.monotonic() >= deadline:
                raise AssertionError("synthetic process tree did not become ready")
            await asyncio.sleep(0.02)
        await context.events.phase("operation.phase.synthetic")
        self.ready.set()
        if self.cancel:
            while not context.cancellation.cancellation_requested:
                await asyncio.sleep(0.01)
            await context.cancellation.acknowledge_cancellation()
        else:
            await self.release.wait()
            return "synthetic:completed"
        return None


def _registry(executor: _ProcessExecutor) -> OperationRegistry:
    definition = OperationDefinition(
        definition_id=_DEFINITION,
        request_type=_Request,
        result_type=_Result,
        executor_factory=OperationExecutorFactory(
            request_type=_Request, executor_type=_ProcessExecutor, build=lambda: executor
        ),
        phase_codes=("operation.phase.synthetic",),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.COOPERATIVE,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset({OperationOwnedResource.PROCESS}),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.REQUEST_CANCEL,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.synthetic.process.request", schema_version=1, model_type=_Request
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.synthetic.process.result", schema_version=1, model_type=_Result
        ),
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "cancel", "shutdown"])
async def test_supervisor_settles_only_after_native_job_descendants_stop(tmp_path: Path, outcome: str) -> None:
    import win32api
    import win32event

    executor = _ProcessExecutor(tmp_path, cancel=outcome != "success")
    storage_root = tmp_path / "synthetic-state"
    journal = OperationJournalRepository(storage_root=storage_root)
    leases = OperationLeaseFilesystemRepository(storage_root=storage_root)
    supervisor = OperationSupervisor(
        registry=_registry(executor),
        authority_operation=unread_authority_operation(),
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=None,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=1),
        cleanup_timeout=timedelta(seconds=5),
    )
    operation_id = "3" * 64
    handles: list[int] = []
    try:
        await supervisor.submit(
            OperationRequest[BaseModel](definition_id=_DEFINITION, subject_ref="synthetic", payload=_Request()),
            operation_id=operation_id,
        )
        await supervisor.start(operation_id)
        await asyncio.wait_for(executor.ready.wait(), timeout=10)
        assert executor.scope is not None
        members = executor.scope.active_process_ids()
        assert len(members) >= 2
        for pid in members:
            handle = win32api.OpenProcess(0x100000, False, pid)
            handles.append(handle)
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        if outcome == "shutdown":
            await asyncio.wait_for(supervisor.shutdown(), timeout=10)
        elif outcome == "cancel":
            await supervisor.request_cancel(operation_id)
        else:
            executor.release.set()
        terminal = await asyncio.wait_for(supervisor.settled(operation_id), timeout=10)
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        expected = (
            OperationTerminalCondition.SUCCEEDED if outcome == "success" else OperationTerminalCondition.CANCELLED
        )
        assert terminal.terminal_condition is expected
        assert terminal.effect is OperationEffect.NONE
        # Exact retained handles verify death, rather than a fast-return or PID
        # absence heuristic. Fallback test cleanup has not run at this point.
        assert all(win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_OBJECT_0 for handle in handles)
        assert executor.scope.active_process_ids() == ()
        released = await leases.inspect(
            operation_conflict_scope_reference(definition_id=_DEFINITION, subject_ref="synthetic"),
            operation_id,
            observed_at=datetime.now(UTC),
        )
        assert released.disposition is OperationLeaseObservationDisposition.ABSENT
    finally:
        executor.release.set()
        try:
            await asyncio.wait_for(supervisor.shutdown(), timeout=10)
        finally:
            try:
                executor.cleanup_fixture()
            finally:
                for handle in handles:
                    win32api.CloseHandle(handle)
