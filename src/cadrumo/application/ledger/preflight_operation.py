"""Registered encrypted ledger preflight for one exact profile period."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.public_period import PublicPeriod
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .check_operation import LedgerCheckIssueProjection
from .preflight import LedgerPreflightReport, preflight_ledger_tax_readiness
from .read_access import resolve_ledger_read_access

LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID = "ledger.preflight"


class LedgerPreflightRequest(CredentialFreeOperationRequest):
    """The exact profile and mandatory canonical period for one preflight."""

    profile_id: UUID
    period: PublicPeriod


class LedgerPreflightProjection(BaseModel):
    """Closed encrypted copy of every canonical preflight report fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    period: PublicPeriod
    bucket_id: str
    checked_transaction_count: NonNegativeInt
    issues: tuple[LedgerCheckIssueProjection, ...]
    ready: bool

    @model_validator(mode="after")
    def consistent_report(self) -> LedgerPreflightProjection:
        """Refuse mixed-profile and contradictory historical result frames."""
        if self.bucket_id != str(self.profile_id):
            raise ValueError("ledger preflight bucket does not match profile")
        if self.ready != (not self.issues):
            raise ValueError("ledger preflight verdict does not match findings")
        return self

    @classmethod
    def from_report(cls, report: LedgerPreflightReport, *, profile_id: UUID) -> LedgerPreflightProjection:
        """Copy the canonical report without recomputing its findings."""
        return cls(
            profile_id=profile_id,
            period=PublicPeriod.from_period(report.period),
            bucket_id=str(report.bucket_id),
            checked_transaction_count=report.checked_transaction_count,
            issues=tuple(LedgerCheckIssueProjection.from_issue(issue) for issue in report.issues),
            ready=report.ready,
        )

    def to_report(self) -> LedgerPreflightReport:
        """Restore the canonical report for existing presentation."""
        report = LedgerPreflightReport(
            bucket_id=self.bucket_id,
            period=self.period.to_period(),
            checked_transaction_count=self.checked_transaction_count,
            issues=tuple(issue.to_issue() for issue in self.issues),
        )
        if report.ready != self.ready:
            raise ValueError("ledger preflight verdict changed during reconstruction")
        return report


class LedgerPreflightExecutor:
    """Read one period under the retained exact-profile authority pin."""

    def __init__(self, ports: LedgerActionPortsFactory) -> None:
        """Retain explicit profile-bound ledger service composition."""
        self._ports = ports

    async def execute(
        self, request: OperationRequest[LedgerPreflightRequest], context: OperationExecutorContext
    ) -> str:
        """Capture the canonical query and publish an encrypted no-effect result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID)

        def read() -> LedgerPreflightProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            report = preflight_ledger_tax_readiness(
                bucket_id=bucket_id,
                period=payload.period.to_period(),
                transaction_repository=ports.transaction_repository,
                usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
                operation=operation,
            )
            if report.bucket_id != bucket_id or report.period != payload.period.to_period():
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return LedgerPreflightProjection.from_report(report, profile_id=payload.profile_id)

        return await capture_read_result(context, read, task_name="ledger-preflight")


def build_ledger_preflight_definition(ports: LedgerActionPortsFactory) -> OperationDefinition:
    """Register a period-specific canonical read with no mutation authority."""
    return OperationDefinition(
        definition_id=LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
        request_type=LedgerPreflightRequest,
        result_type=LedgerPreflightProjection,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerPreflightRequest,
            executor_type=LedgerPreflightExecutor,
            build=lambda: LedgerPreflightExecutor(ports),
        ),
        phase_codes=(LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_ledger_preflight_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind every lifecycle action to the canonical requested period."""
    if request.definition_id != LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerPreflightRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    return resolve_ledger_read_access(
        request, context, profile_id=payload.profile_id, periods=frozenset({payload.period.to_period()})
    )


def build_ledger_preflight_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict versioned schemas and exact-period disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerPreflightProjection,
        access_resolver=resolve_ledger_preflight_access,
    )
