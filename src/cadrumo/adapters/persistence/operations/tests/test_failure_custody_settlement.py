"""Financial operand cleanup precedes every executor-failure receipt."""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import override

import pytest
from pydantic import BaseModel, Field

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from cadrumo.adapters.persistence.operations.typed_financial_operand_custody import (
    OperationTypedFinancialOperandCustodyFilesystemRepository,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.errors import OperationSubjectBusyError, OperationUnsettledError
from cadrumo.application.operations.financial_operand_contract import (
    CredentialFreeFinancialOperationRequest,
    OperationTransientFinancialOperandRequirementV1,
)
from cadrumo.application.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyCheckpointV1,
    OperationFinancialOperandCustodyState,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.operation_definition import OperationDefinition, OperationExecutorFactory
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.application.operations.tests.financial_operand_models import (
    FinancialOperandBaseline,
    FinancialOperandBatch,
    financial_operand_declaration,
)
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 26, 9, tzinfo=UTC)
_DEFINITION_ID = "operation.financial.operand.failure-custody"
_OPERATION_ID = "4" * 64
_DECLARATION = financial_operand_declaration()


class _Request(CredentialFreeFinancialOperationRequest):
    """Encrypted request with no financial operand material."""

    model_config = STRICT_FROZEN_CONFIG

    subject: str = Field(min_length=1)


class _FailureAfterGrantExecutor:
    """Hold one accepted operand, then raise the selected registered or ordinary failure."""

    def __init__(self, *, registered_refusal: bool) -> None:
        self.registered_refusal = registered_refusal
        self.requirement: OperationTransientFinancialOperandRequirementV1 | None = None

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> None:
        """Use real declared-input custody before exercising supervisor failure settlement."""
        del request
        async with context.typed_financial_operand.consume(FinancialOperandBatch) as operand:
            try:
                assert operand.values == (Decimal("1234.56"), Decimal("-4.12"), Decimal("0.125"))
                if self.registered_refusal:
                    raise OperationSubjectBusyError()
                raise RuntimeError("synthetic executor failure")
            finally:
                del operand


class _GatedReleaseCustodyRepository(OperationTypedFinancialOperandCustodyFilesystemRepository):
    """Use the durable adapter, with one release gate to observe settlement ordering."""

    def __init__(self, *, root: Path, fail_release: bool = False) -> None:
        super().__init__(root=root)
        self.fail_release = fail_release
        self.release_persisted = asyncio.Event()
        self.allow_buffer_release = asyncio.Event()

    @override
    async def advance(
        self,
        predecessor: OperationFinancialOperandCustodyCheckpointV1,
        successor: OperationFinancialOperandCustodyCheckpointV1,
    ) -> None:
        if successor.state is OperationFinancialOperandCustodyState.RELEASED:
            if self.fail_release:
                raise OSError("synthetic custody release failure")
            await super().advance(predecessor, successor)
            self.release_persisted.set()
            await self.allow_buffer_release.wait()
            return
        await super().advance(predecessor, successor)


def _capabilities() -> OperationCapabilities:
    """Declare the exact supervisor contract needed for one sensitive wait."""
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.NONE,
        baseline=OperationBaselinePolicy.REQUEST_BOUND,
        request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
        sensitive_input=OperationSensitiveInputPolicy.NONE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _supervisor(
    *,
    executor: _FailureAfterGrantExecutor,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceRepository,
    custody: _GatedReleaseCustodyRepository,
) -> OperationSupervisor:
    """Compose the real supervisor and encrypted request/journal adapters."""
    definition = OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=_Request,
        result_type=None,
        executor_factory=OperationExecutorFactory(
            request_type=_Request,
            executor_type=_FailureAfterGrantExecutor,
            build=lambda: executor,
        ),
        phase_codes=("operation.phase.declared",),
        interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
        transient_financial_operand=_DECLARATION,
        public_error_detail=False,
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{_DEFINITION_ID}.request",
            schema_version=1,
            model_type=_Request,
        ),
    )
    supervisor = OperationSupervisor(
        authority_operation=unread_authority_operation(),
        registry=OperationRegistry(definitions=(definition,), public_registrations=(registration,)),
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: _NOW,
        lease_duration=timedelta(minutes=10),
        typed_financial_operand_custody=custody,
    )
    return supervisor


def _request() -> OperationRequest[BaseModel]:
    """Build the registered request carried through real secure storage."""
    return OperationRequest[BaseModel](
        definition_id=_DEFINITION_ID,
        subject_ref="subject:financial-operand-failure",
        payload=_Request(subject="modelo-303-regularizacion", financial_baseline_ref="d" * 64),
        idempotency_key=None,
    )


@pytest.mark.parametrize("registered_refusal", (True, False), ids=("registered-refusal", "ordinary-failure"))
def test_executor_failure_receipt_waits_for_financial_operand_release(tmp_path: Path, registered_refusal: bool) -> None:
    """A terminal receipt stays absent while the real custody cleanup is unfinished."""
    executor = _FailureAfterGrantExecutor(registered_refusal=registered_refusal)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        custody = _GatedReleaseCustodyRepository(root=tmp_path / "custody")
        supervisor = _supervisor(
            executor=executor,
            journal=OperationJournalRepository(storage_root=storage_root),
            leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
            operands=operation_secure_reference_repository(objects=profile.repository),
            custody=custody,
        )

        async def run() -> tuple[
            OperationPersistedSnapshot,
            OperationPersistedSnapshot,
            OperationFinancialOperandCustodyCheckpointV1 | None,
        ]:
            operation_id = await supervisor.submit(_request(), operation_id=_OPERATION_ID)
            await supervisor.bind_typed_financial_operand(
                operation_id,
                FinancialOperandBatch(
                    baseline=FinancialOperandBaseline(baseline_id="d" * 64),
                    values=(Decimal("1234.56"), Decimal("-4.12"), Decimal("0.125")),
                ),
            )
            executor.requirement = (await supervisor.inspect(operation_id)).financial_requirement
            await supervisor.start(operation_id)
            await asyncio.wait_for(custody.release_persisted.wait(), timeout=5)
            before_cleanup_returns = await supervisor.inspect(operation_id)
            requirement = executor.requirement
            assert requirement is not None
            checkpoint_during_cleanup = await custody.read(requirement.handoff_id)
            custody.allow_buffer_release.set()
            terminal = await supervisor.settled(operation_id)
            return before_cleanup_returns, terminal, checkpoint_during_cleanup

        before_cleanup_returns, terminal, checkpoint_during_cleanup = asyncio.run(run())

        assert before_cleanup_returns.lifecycle is OperationLifecycle.RUNNING
        assert before_cleanup_returns.terminal_receipt is None
        assert checkpoint_during_cleanup is not None
        assert checkpoint_during_cleanup.state is OperationFinancialOperandCustodyState.RELEASED
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        receipt = terminal.terminal_receipt
        assert receipt is not None
        assert receipt.effect is OperationEffect.NONE
        if registered_refusal:
            assert receipt.condition is OperationTerminalCondition.REFUSED
            assert receipt.refusal_ref == "REFUSED_OPERATION_SUBJECT_BUSY"
        else:
            assert receipt.condition is OperationTerminalCondition.FAILED
            assert receipt.failure_error_code is None
            assert receipt.diagnostic_ref is not None
        requirement = executor.requirement
        assert requirement is not None
        checkpoint = asyncio.run(custody.read(requirement.handoff_id))
        assert checkpoint is not None and checkpoint.state is OperationFinancialOperandCustodyState.RELEASED


def test_failed_financial_operand_cleanup_does_not_publish_executor_failure_receipt(tmp_path: Path) -> None:
    """A failed cleanup leaves the operation unsettled instead of claiming a refusal."""
    executor = _FailureAfterGrantExecutor(registered_refusal=True)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        custody = _GatedReleaseCustodyRepository(root=tmp_path / "custody", fail_release=True)
        supervisor = _supervisor(
            executor=executor,
            journal=OperationJournalRepository(storage_root=storage_root),
            leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
            operands=operation_secure_reference_repository(objects=profile.repository),
            custody=custody,
        )

        async def run() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id=_OPERATION_ID)
            await supervisor.bind_typed_financial_operand(
                operation_id,
                FinancialOperandBatch(
                    baseline=FinancialOperandBaseline(baseline_id="d" * 64),
                    values=(Decimal("1234.56"), Decimal("-4.12"), Decimal("0.125")),
                ),
            )
            executor.requirement = (await supervisor.inspect(operation_id)).financial_requirement
            await supervisor.start(operation_id)
            with pytest.raises(OperationUnsettledError):
                await supervisor.settled(operation_id)
            return await supervisor.inspect(operation_id)

        unsettled = asyncio.run(run())

        assert unsettled.lifecycle is OperationLifecycle.RUNNING
        assert unsettled.terminal_receipt is None
        requirement = executor.requirement
        assert requirement is not None
        checkpoint = asyncio.run(custody.read(requirement.handoff_id))
        assert checkpoint is not None
        assert checkpoint.state is OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED


@pytest.mark.parametrize("registered_refusal", (True, False), ids=("registered-refusal", "ordinary-failure"))
def test_executor_failure_log_record_carries_the_raising_frame(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, registered_refusal: bool
) -> None:
    """The settlement log keeps the executor frame that raised, next to the receipt's correlation."""
    executor = _FailureAfterGrantExecutor(registered_refusal=registered_refusal)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        custody = _GatedReleaseCustodyRepository(root=tmp_path / "custody")
        custody.allow_buffer_release.set()
        supervisor = _supervisor(
            executor=executor,
            journal=OperationJournalRepository(storage_root=storage_root),
            leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
            operands=operation_secure_reference_repository(objects=profile.repository),
            custody=custody,
        )

        async def run() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id=_OPERATION_ID)
            await supervisor.bind_typed_financial_operand(
                operation_id,
                FinancialOperandBatch(
                    baseline=FinancialOperandBaseline(baseline_id="d" * 64),
                    values=(Decimal("1234.56"), Decimal("-4.12"), Decimal("0.125")),
                ),
            )
            executor.requirement = (await supervisor.inspect(operation_id)).financial_requirement
            await supervisor.start(operation_id)
            return await supervisor.settled(operation_id)

        with caplog.at_level(logging.WARNING, logger="cadrumo.application.operations._supervisor_execution"):
            terminal = asyncio.run(run())

    receipt = terminal.terminal_receipt
    assert receipt is not None
    correlation = receipt.refusal_ref if registered_refusal else receipt.diagnostic_ref
    assert correlation is not None
    records = [
        record
        for record in caplog.records
        if record.name == "cadrumo.application.operations._supervisor_execution"
        and f"operation={_OPERATION_ID}" in record.getMessage()
        and correlation in record.getMessage()
    ]
    assert len(records) == 1
    exc_info = records[0].exc_info
    assert exc_info is not None
    frames = [(frame.f_code.co_filename, frame.f_code.co_name) for frame, _ in traceback.walk_tb(exc_info[2])]
    assert (__file__, "execute") == frames[-1]
