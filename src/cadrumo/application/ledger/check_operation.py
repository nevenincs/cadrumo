"""Registered encrypted ledger check under whole-profile read authority."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.invoices.service import LinkInconsistency
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
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
from .check_query import LedgerCheckV1, read_ledger_check
from .preflight import LedgerPreflightIssue, LedgerPreflightIssueReason
from .read_access import resolve_ledger_read_access

LEDGER_CHECK_OPERATION_DEFINITION_ID = "ledger.check"


class LedgerCheckRequest(CredentialFreeOperationRequest):
    """Exact profile and optional period selecting only the preflight sweep."""

    profile_id: UUID
    period: PublicPeriod | None = None


class LedgerCheckIssueProjection(BaseModel):
    """Closed wire shape for canonical preflight issue prose."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId | Literal["__period__"]
    reason: LedgerPreflightIssueReason
    detail: str = Field(min_length=1, max_length=512)

    @classmethod
    def from_issue(cls, issue: LedgerPreflightIssue) -> LedgerCheckIssueProjection:
        """Copy already canonical text without elision or reinterpretation."""
        return cls(transaction_id=issue.transaction_id, reason=issue.reason, detail=issue.detail)

    def to_issue(self) -> LedgerPreflightIssue:
        """Rebuild the canonical issue after the wire cap has been checked."""
        issue = LedgerPreflightIssue(
            transaction_id=self.transaction_id,
            reason=self.reason,
            detail=self.detail,
        )
        if issue.detail != self.detail:
            raise ValueError("ledger check issue text changed during reconstruction")
        return issue


class LedgerCheckProjection(BaseModel):
    """Strict encrypted snapshot of every canonical check fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    period: PublicPeriod | None
    bucket_id: str
    periods: tuple[str, ...]
    checked_transaction_count: NonNegativeInt
    issues: tuple[LedgerCheckIssueProjection, ...]
    link_inconsistencies: tuple[LinkInconsistency, ...]
    ready: bool

    @model_validator(mode="after")
    def consistent_check(self) -> LedgerCheckProjection:
        """Refuse a forged profile or a verdict contradicted by findings."""
        if self.bucket_id != str(self.profile_id):
            raise ValueError("ledger check bucket does not match profile")
        if self.ready != (not self.issues and not self.link_inconsistencies):
            raise ValueError("ledger check verdict does not match findings")
        if self.period is not None and self.periods != (str(self.period.to_period()),):
            raise ValueError("ledger check periods do not match selection")
        return self

    @classmethod
    def from_check(
        cls, check: LedgerCheckV1, *, profile_id: UUID, period: PublicPeriod | None
    ) -> LedgerCheckProjection:
        """Carry the canonical query result without another readiness decision."""
        return cls.model_validate(
            {
                **check.model_dump(mode="python", exclude={"issues"}),
                "profile_id": profile_id,
                "period": period,
                "issues": tuple(LedgerCheckIssueProjection.from_issue(issue) for issue in check.issues),
            }
        )

    def to_check(self) -> LedgerCheckV1:
        """Restore every canonical field for the existing CLI presentation."""
        return LedgerCheckV1.model_validate(
            {
                **self.model_dump(exclude={"profile_id", "period", "issues"}),
                "issues": tuple(issue.to_issue() for issue in self.issues),
            }
        )


class LedgerCheckExecutor:
    """Read both catalogues and preflight inside retained profile custody."""

    def __init__(self, ports: LedgerActionPortsFactory) -> None:
        """Retain the explicit profile-bound ledger port factory."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerCheckRequest], context: OperationExecutorContext) -> str:
        """Store an encrypted no-effect result after the complete canonical query."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_CHECK_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_CHECK_OPERATION_DEFINITION_ID)

        def read() -> LedgerCheckProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if (
                ports.transaction_repository.bucket_id != bucket_id
                or ports.invoice_repository.bucket_id != bucket_id
                or ports.operation is not operation
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            check = read_ledger_check(
                bucket_id=bucket_id,
                transactions=ports.transaction_repository.load(),
                ports=InvoiceCatalogueReadPorts(
                    invoice_reader=ports.invoice_repository,
                    transaction_reader=ports.transaction_repository,
                ),
                operation=operation,
                period=payload.period.to_period() if payload.period is not None else None,
            )
            return LedgerCheckProjection.from_check(check, profile_id=payload.profile_id, period=payload.period)

        return await capture_read_result(context, read, task_name="ledger-check")


def build_ledger_check_definition(ports: LedgerActionPortsFactory) -> OperationDefinition:
    """Register the real canonical read without mutation capability."""
    return OperationDefinition(
        definition_id=LEDGER_CHECK_OPERATION_DEFINITION_ID,
        request_type=LedgerCheckRequest,
        result_type=LedgerCheckProjection,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerCheckRequest,
            executor_type=LedgerCheckExecutor,
            build=lambda: LedgerCheckExecutor(ports),
        ),
        phase_codes=(LEDGER_CHECK_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_ledger_check_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require independent all-period authority because links remain global."""
    if request.definition_id != LEDGER_CHECK_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerCheckRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_check_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict versioned schemas to whole-profile read access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerCheckProjection,
        access_resolver=resolve_ledger_check_access,
    )
