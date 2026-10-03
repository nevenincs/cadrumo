"""Registered encrypted ledger status under whole-profile read authority."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, field_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..modelo.verification_repository_ports import VerificationRepositoryBundleFactory
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
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .actions_manual import summarize_manual_transactions
from .models import LedgerStatusReport
from .readiness_query import LedgerReadinessIssueV1, read_ledger_readiness
from .stale_filing_query import LedgerStaleFilingV1, read_stale_ledger_filings

LEDGER_STATUS_OPERATION_DEFINITION_ID = "ledger.status"


class LedgerStatusRequest(CredentialFreeOperationRequest):
    """Optional money/readiness period; counts and filing history remain global."""

    profile_id: UUID
    period: PublicPeriod | None = None


class LedgerStatusReadinessIssueProjection(BaseModel):
    """JSON-stable readiness facts with exact decimal strings for encrypted storage."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: str
    reason: str
    detail: str
    transaction_present: bool
    business_classification: str | None = None
    category_id: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None

    @field_validator("taxable_base", "iva_rate", "iva_amount")
    @classmethod
    def _require_decimal_text(cls, value: str | None) -> str | None:
        """Reject malformed decimal text without ever routing through float."""
        if value is not None:
            try:
                parsed = Decimal(value)
            except InvalidOperation as error:
                raise ValueError("readiness issue decimal facts must be decimal strings") from error
            if not parsed.is_finite():
                raise ValueError("readiness issue decimal facts must be finite")
        return value

    @classmethod
    def from_issue(cls, issue: LedgerReadinessIssueV1) -> LedgerStatusReadinessIssueProjection:
        """Project one canonical readiness issue into a strict JSON-safe shape."""
        return cls(
            transaction_id=issue.transaction_id,
            reason=issue.reason,
            detail=issue.detail,
            transaction_present=issue.transaction_present,
            business_classification=issue.business_classification,
            category_id=issue.category_id,
            taxable_base=str(issue.taxable_base) if issue.taxable_base is not None else None,
            iva_rate=str(issue.iva_rate) if issue.iva_rate is not None else None,
            iva_amount=str(issue.iva_amount) if issue.iva_amount is not None else None,
        )

    def to_issue(self) -> LedgerReadinessIssueV1:
        """Restore the canonical issue using exact ``Decimal(str)`` conversion."""
        return LedgerReadinessIssueV1(
            transaction_id=self.transaction_id,
            reason=self.reason,
            detail=self.detail,
            transaction_present=self.transaction_present,
            business_classification=self.business_classification,
            category_id=self.category_id,
            taxable_base=Decimal(self.taxable_base) if self.taxable_base is not None else None,
            iva_rate=Decimal(self.iva_rate) if self.iva_rate is not None else None,
            iva_amount=Decimal(self.iva_amount) if self.iva_amount is not None else None,
        )


class LedgerStatusProjection(BaseModel):
    """Strict encrypted snapshot preserving all existing status result facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    period: PublicPeriod | None
    business_income_total: str
    business_expense_total: str
    business_net_total: str
    total_count: NonNegativeInt
    active_count: NonNegativeInt
    archived_count: NonNegativeInt
    stashed_count: NonNegativeInt
    split_count: NonNegativeInt
    pending_review_count: NonNegativeInt
    reviewed_count: NonNegativeInt
    skipped_count: NonNegativeInt
    checked_transaction_count: NonNegativeInt
    readiness_issue_count: NonNegativeInt
    unconverted_currency_count: NonNegativeInt
    ready: bool | None
    readiness_issues: tuple[LedgerStatusReadinessIssueProjection, ...]
    stale_filings: tuple[LedgerStaleFilingV1, ...]

    @classmethod
    def from_report(
        cls,
        report: LedgerStatusReport,
        *,
        readiness_issues: tuple[LedgerReadinessIssueV1, ...],
        stale_filings: tuple[LedgerStaleFilingV1, ...],
    ) -> LedgerStatusProjection:
        """Project canonical facts without a second totals or readiness policy."""
        values = report.model_dump(exclude={"bucket_id", "period"})
        return cls.model_validate(
            {
                **values,
                "profile_id": UUID(report.bucket_id),
                "period": PublicPeriod.from_period(report.period) if report.period is not None else None,
                "readiness_issues": tuple(
                    LedgerStatusReadinessIssueProjection.from_issue(issue) for issue in readiness_issues
                ),
                "stale_filings": stale_filings,
            }
        )

    def to_report(self) -> LedgerStatusReport:
        """Restore the canonical summary for frontend rendering."""
        values = self.model_dump(exclude={"profile_id", "period", "readiness_issues", "stale_filings"})
        return LedgerStatusReport.model_validate(
            {
                **values,
                "bucket_id": str(self.profile_id),
                "period": self.period.to_period() if self.period is not None else None,
            }
        )


class LedgerStatusExecutor:
    """Read status only inside the retained exact-profile worker."""

    def __init__(self, ports: LedgerActionPortsFactory, repositories: VerificationRepositoryBundleFactory) -> None:
        """Retain the explicit profile-port factories used during execution."""
        self._ports = ports
        self._repositories = repositories

    async def execute(self, request: OperationRequest[LedgerStatusRequest], context: OperationExecutorContext) -> str:
        """Capture canonical queries and publish an encrypted no-effect result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_STATUS_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_STATUS_OPERATION_DEFINITION_ID)

        def read() -> LedgerStatusProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            repositories = self._repositories(bucket_id, operation=operation)
            if (
                ports.transaction_repository.bucket_id != bucket_id
                or repositories.calculation.bucket_id != bucket_id
                or repositories.work_unit.bucket_id != bucket_id
                or ports.operation is not operation
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            transactions = ports.transaction_repository.load()
            period = payload.period.to_period() if payload.period is not None else None
            report = summarize_manual_transactions(
                bucket_id=bucket_id, period=period, ports=ports, catalogue=transactions
            )
            readiness = (
                read_ledger_readiness(
                    bucket_id=bucket_id,
                    period=period,
                    transaction_repository=ports.transaction_repository,
                    usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
                    operation=operation,
                )
                if period is not None
                else ()
            )
            stale = read_stale_ledger_filings(
                bucket_id=bucket_id,
                revisions=repositories.calculation.load(operation=operation).revisions,
                work_units=repositories.work_unit.load(),
                transactions=transactions,
            )
            return LedgerStatusProjection.from_report(report, readiness_issues=readiness, stale_filings=stale)

        return await capture_read_result(context, read, task_name="ledger-status")


def build_ledger_status_definition(
    ports: LedgerActionPortsFactory, repositories: VerificationRepositoryBundleFactory
) -> OperationDefinition:
    """Register the existing read services without mutation or provider authority."""
    return OperationDefinition(
        definition_id=LEDGER_STATUS_OPERATION_DEFINITION_ID,
        request_type=LedgerStatusRequest,
        result_type=LedgerStatusProjection,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerStatusRequest,
            executor_type=LedgerStatusExecutor,
            build=lambda: LedgerStatusExecutor(ports, repositories),
        ),
        phase_codes=(LEDGER_STATUS_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_ledger_status_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require all-period permission even when money totals select one period."""
    from .read_access import resolve_ledger_read_access

    payload = request.payload
    if request.definition_id != LEDGER_STATUS_OPERATION_DEFINITION_ID or not isinstance(payload, LedgerStatusRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def build_ledger_status_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind current strict schemas and the whole-profile disclosure policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerStatusProjection,
        access_resolver=resolve_ledger_status_access,
    )
