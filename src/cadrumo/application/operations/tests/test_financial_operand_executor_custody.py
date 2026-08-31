"""A registered executor reaching the transient financial operand broker.

The declaration contract, the custody state machine and the durable checkpoint
repository each stand on their own. What this exercises is the composition:
one real registered operation, started through the production supervisor over
real filesystem and encrypted adapters, whose executor opens its own declared
wait, is answered by the operator submission port, and reads the amount back.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from ....adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from ....core import STRICT_FROZEN_CONFIG
from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ....tests.secure_sql import isolated_runtime_profile
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..financial_operand import (
    OperationFinancialOperandRefusalReason,
    OperationTransientFinancialOperandAcknowledgement,
    OperationTransientFinancialOperandDeclaration,
    OperationTransientFinancialOperandDelivery,
    OperationTransientFinancialOperandRefusal,
    OperationTransientFinancialOperandRequirement,
)
from ..financial_operand_custody import OperationFinancialOperandCustodyState
from ..models import OperationRequest
from ..owner import OperationExecutorContext
from ..registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from ..supervisor import OperationSupervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 26, 9, tzinfo=UTC)
_DEFINITION_ID = "operation.financial.operand.executor"
_OPERATION_ID = "4" * 64

_DECLARATION = OperationTransientFinancialOperandDeclaration(
    operand_kind="regularizacion.cuota",
    currency="EUR",
    scale=2,
    minimum=Decimal("0.00"),
    maximum=Decimal("5000.00"),
    lifetime=timedelta(minutes=5),
)
_IN_BOUNDS = Decimal("1234.56")
_OUT_OF_BOUNDS = Decimal("5000.01")

type _SubmissionPort = Callable[
    [OperationTransientFinancialOperandRequirement, Decimal],
    Awaitable[OperationTransientFinancialOperandDelivery],
]


class FinancialOperandRequest(BaseModel):
    """Concrete request carrying no operand material of its own."""

    model_config = STRICT_FROZEN_CONFIG

    subject: str = Field(min_length=1)


class FinancialOperandExecutor:
    """Declare one operand wait, take both answers, and read the accepted amount."""

    def __init__(self) -> None:
        self.submission_port: _SubmissionPort | None = None
        self.refused: OperationTransientFinancialOperandDelivery | None = None
        self.accepted: OperationTransientFinancialOperandDelivery | None = None
        self.observed_amount: Decimal | None = None
        self.requirement: OperationTransientFinancialOperandRequirement | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> None:
        """Open the declared wait and settle it from the operator submission port."""
        del request
        if self.submission_port is None:
            raise RuntimeError("executor has no operator submission port")
        requirement = context.financial_operand.declare_requirement(_DECLARATION)
        self.requirement = requirement
        self.refused = await self.submission_port(requirement, _OUT_OF_BOUNDS)
        self.accepted = await self.submission_port(requirement, _IN_BOUNDS)
        access = context.financial_operand.grant_access(requirement)
        self.observed_amount = access.declared_operand(requirement)


def _capabilities() -> OperationCapabilities:
    """Declare the contract a transient financial operand operation requires."""
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _registry(executor: FinancialOperandExecutor) -> OperationRegistry:
    """Register one production-shaped definition declaring the operand."""
    definition = OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=FinancialOperandRequest,
        result_type=None,
        executor_factory=OperationExecutorFactory(
            request_type=FinancialOperandRequest,
            executor_type=FinancialOperandExecutor,
            build=lambda: executor,
        ),
        phase_codes=("operation.phase.declared",),
        interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
        transient_financial_operands=(_DECLARATION,),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.financial.operand.executor.request",
            schema_version=1,
            model_type=FinancialOperandRequest,
        ),
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _supervisor(
    *,
    executor: FinancialOperandExecutor,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceRepository,
    custody: OperationFinancialOperandCustodyFilesystemRepository,
) -> OperationSupervisor:
    """Construct the public supervisor over the real persistence adapters."""
    return OperationSupervisor(
        registry=_registry(executor),
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: _NOW,
        lease_duration=timedelta(minutes=10),
        financial_operand_custody=custody,
    )


def _request() -> OperationRequest[BaseModel]:
    """Create one real encrypted request submission."""
    return OperationRequest[BaseModel](
        definition_id=_DEFINITION_ID,
        subject_ref="subject:financial-operand",
        payload=FinancialOperandRequest(subject="modelo-303-regularizacion"),
        idempotency_key=None,
    )


def test_registered_executor_reaches_the_transient_financial_operand_broker(tmp_path: Path) -> None:
    """A started executor is refused an out-of-bounds amount and granted an in-bounds one."""
    executor = FinancialOperandExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        custody = OperationFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
        supervisor = _supervisor(
            executor=executor,
            journal=OperationJournalRepository(storage_root=storage_root),
            leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
            operands=operation_secure_reference_repository(objects=profile.repository),
            custody=custody,
        )
        executor.submission_port = supervisor.submit_transient_financial_operand

        operation_id = asyncio.run(supervisor.submit(_request(), operation_id=_OPERATION_ID))
        asyncio.run(supervisor.start(operation_id))

        requirement = executor.requirement
        assert requirement is not None
        assert requirement.identity.operation_id == operation_id
        assert requirement.operand_kind == _DECLARATION.operand_kind
        assert requirement.expires_at == _NOW + _DECLARATION.lifetime

        refused = executor.refused
        assert isinstance(refused, OperationTransientFinancialOperandRefusal)
        assert refused.reason is OperationFinancialOperandRefusalReason.OUT_OF_DECLARED_RANGE
        assert refused.requirement == requirement

        accepted = executor.accepted
        assert isinstance(accepted, OperationTransientFinancialOperandAcknowledgement)
        assert accepted.requirement == requirement
        assert executor.observed_amount == _IN_BOUNDS

        settled = asyncio.run(custody.read(requirement.interaction_id))
        assert settled is not None
        assert settled.state is OperationFinancialOperandCustodyState.RELEASED
        assert "amount" not in settled.model_dump_json()
