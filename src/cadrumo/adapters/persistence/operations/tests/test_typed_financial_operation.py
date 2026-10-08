"""Complete typed custody through the production supervisor and real journals."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from .....application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .....application.operations.financial_operand_contract import (
    CredentialFreeFinancialOperationRequest,
    OperationTransientFinancialOperandDeclarationV1,
    OperationTransientFinancialOperandRequirementV1,
    financial_operand_model_identity,
)
from .....application.operations.frontend_requests import OperationObservationRequestV1, OperationObservationSuccessV1
from .....application.operations.models import OperationRequest
from .....application.operations.observation import OperationObservationService
from .....application.operations.operation_definition import OperationDefinition, OperationExecutorFactory
from .....application.operations.owner import OperationExecutorContext
from .....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from .....application.operations.supervisor import OperationSupervisor
from .....application.operations.tests.authority_test_support import unread_authority_operation
from .....application.operations.tests.financial_operand_models import FinancialOperandBaseline, FinancialOperandBatch
from .....core.models import STRICT_FROZEN_CONFIG
from .....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..journal import OperationJournalRepository
from ..lease import OperationLeaseFilesystemRepository
from ..secure_references import operation_secure_reference_repository
from ..typed_financial_operand_custody import OperationTypedFinancialOperandCustodyFilesystemRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_NOW = datetime(2026, 10, 5, tzinfo=UTC)


class _SafeRequest(CredentialFreeFinancialOperationRequest):
    """Only opaque immutable baseline coordinates cross admission."""


class _SafeResult(BaseModel):
    """The synthetic executor reports only its batch size."""

    model_config = STRICT_FROZEN_CONFIG
    count: int


class _Executor:
    """Read the exact batch once through the actual executor context."""

    async def execute(self, request: OperationRequest[_SafeRequest], context: OperationExecutorContext) -> str:
        async with context.typed_financial_operand.consume(FinancialOperandBatch) as batch:
            try:
                assert batch.baseline.baseline_id == request.payload.financial_baseline_ref
                assert batch.values == (Decimal("93847562.19"), Decimal("-17.23"), Decimal("0.125"))
                count = len(batch.values)
            finally:
                del batch
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(_SafeResult(count=count), written_at=_NOW)


def _registry() -> OperationRegistry:
    def baseline(operand: BaseModel) -> BaseModel:
        return cast(FinancialOperandBatch, operand).baseline

    def reference(operand: BaseModel) -> str:
        return cast(FinancialOperandBaseline, operand).baseline_id

    async def receipt(requirement: OperationTransientFinancialOperandRequirementV1) -> None:
        return None

    declaration = OperationTransientFinancialOperandDeclarationV1(
        operand_type=FinancialOperandBatch,
        baseline_type=FinancialOperandBaseline,
        operand_schema=financial_operand_model_identity(
            schema_id="test.batch", schema_version=1, model_type=FinancialOperandBatch
        ),
        baseline_schema=financial_operand_model_identity(
            schema_id="test.baseline", schema_version=1, model_type=FinancialOperandBaseline
        ),
        baseline_accessor=baseline,
        baseline_reference=reference,
        lifetime=timedelta(minutes=1),
        effect_receipt_resolver=receipt,
    )
    definition = OperationDefinition(
        definition_id="test.typed.batch",
        request_type=_SafeRequest,
        result_type=_SafeResult,
        executor_factory=OperationExecutorFactory(request_type=_SafeRequest, executor_type=_Executor, build=_Executor),
        phase_codes=("test.typed.batch",),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
        transient_financial_operand=declaration,
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="test.typed.batch.request", schema_version=2, model_type=_SafeRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="test.typed.batch.result", schema_version=1, model_type=_SafeResult
        ),
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


@pytest.mark.parametrize("cancel", (False, True))
def test_real_supervisor_consumes_or_cancels_a_whole_batch_without_durable_values(tmp_path: Path, cancel: bool) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        journal = OperationJournalRepository(storage_root=tmp_path / "durable")
        custody = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
        supervisor = OperationSupervisor(
            registry=_registry(),
            authority_operation=unread_authority_operation(),
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=tmp_path / "durable"),
            operands=operation_secure_reference_repository(),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=10),
            typed_financial_operand_custody=custody,
        )

        async def exercise() -> None:
            operation_id = await supervisor.submit(
                OperationRequest(
                    definition_id="test.typed.batch",
                    subject_ref="unit",
                    payload=_SafeRequest(financial_baseline_ref="d" * 64),
                )
            )
            await supervisor.bind_typed_financial_operand(
                operation_id,
                FinancialOperandBatch(
                    baseline=FinancialOperandBaseline(baseline_id="d" * 64),
                    values=(Decimal("93847562.19"), Decimal("-17.23"), Decimal("0.125")),
                ),
            )
            observation = OperationObservationService(reader=journal, registry=supervisor.registry)
            before = await observation.observe(
                OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
            )
            assert isinstance(before, OperationObservationSuccessV1)
            assert before.projection.financial_operand_pending and before.projection.cancellable_now
            for updates in (
                {"effect": OperationEffect.UPDATED},
                {"lifecycle": OperationLifecycle.RUNNING},
                {"financial_operand_cancelled_before_delivery": True},
                {
                    "definition_contract": before.projection.definition_contract.model_copy(
                        update={"transient_financial_operand": None}
                    )
                },
            ):
                with pytest.raises(ValidationError):
                    type(before.projection).model_validate({**before.projection.model_dump(), **updates})
            if cancel:
                final = await supervisor.request_cancel(operation_id)
                assert final.terminal_condition is OperationTerminalCondition.CANCELLED
            else:
                await supervisor.start(operation_id)
                final = await supervisor.settled(operation_id)
                assert final.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert final.lifecycle is OperationLifecycle.TERMINAL and final.effect is OperationEffect.NONE
            assert final.financial_requirement is not None
            after = await observation.observe(
                OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
            )
            assert isinstance(after, OperationObservationSuccessV1)
            assert not after.projection.financial_operand_pending and not after.projection.cancellable_now
            assert after.projection.financial_operand_cancelled_before_delivery is cancel
            await supervisor.shutdown()

        asyncio.run(exercise())
        for path in tuple((tmp_path / "durable").rglob("*.json")) + tuple((tmp_path / "custody").rglob("*.json")):
            stored = path.read_text(encoding="utf-8")
            assert "93847562.19" not in stored and "-17.23" not in stored and "0.125" not in stored
