"""Encrypted ledger selection under the exact profile and canonical filter scope."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, PositiveInt, model_validator

from ...core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..review.errors import FilterParseError
from ..review.filter import LedgerReviewFilterSpec
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .actions_manual import ledger_transaction_payload
from .list_query import LedgerTransactionListQuery, query_ledger_transaction_list
from .read_access import resolve_ledger_read_access
from .review_projection import ledger_transaction_review_status
from .transaction_projection import LedgerTransactionProjection, LedgerTransactionReviewProjection

LEDGER_LIST_OPERATION_DEFINITION_ID = "ledger.list"


class LedgerListRequest(BaseModel):
    """Private filter input stored only in the encrypted operand repository."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    filters: tuple[str, ...] = ()
    group: str | None = None
    by_group: bool = False
    limit: PositiveInt | None = None
    offset: NonNegativeInt = 0
    sort_by: LedgerSortField | None = None
    sort_order: LedgerSortOrder = LedgerSortOrder.ASC
    exclude_llm_rejected: bool = False

    def filter_spec(self) -> LedgerReviewFilterSpec:
        """Resolve scope and execution through the same canonical grammar."""
        try:
            return LedgerReviewFilterSpec.from_strings(self.filters)
        except FilterParseError:
            raise ValueError("invalid ledger selection filters") from None

    @model_validator(mode="after")
    def valid_filters(self) -> LedgerListRequest:
        """Refuse invalid clauses without echoing private values in diagnostics."""
        self.filter_spec()
        return self


class LedgerListProjection(BaseModel):
    """Canonical selected rows and truthful paging facts captured in custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: tuple[LedgerTransactionReviewProjection, ...]
    total: NonNegativeInt
    truncated: bool
    offset: NonNegativeInt
    limit: PositiveInt | None
    by_group: bool

    @model_validator(mode="after")
    def consistent_window(self) -> LedgerListProjection:
        """Reject impossible page totals or duplicated canonical rows."""
        available = max(self.total - self.offset, 0)
        shown = available if self.limit is None else min(available, self.limit)
        if len(self.rows) != shown:
            raise ValueError("ledger page length does not match its declared window")
        expected_truncated = self.offset > 0 or (self.limit is not None and self.offset + self.limit < self.total)
        if self.truncated != expected_truncated:
            raise ValueError("ledger page truncation does not match its declared window")
        if len({row.transaction.transaction_id for row in self.rows}) != len(self.rows):
            raise ValueError("ledger page repeats a transaction")
        return self


class LedgerListExecutor:
    """Host the canonical list query without frontend persistence access."""

    def __init__(self, ports: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile port factory."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerListRequest], context: OperationExecutorContext) -> str:
        """Publish selected financial facts as an encrypted no-effect result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_LIST_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_LIST_OPERATION_DEFINITION_ID)

        def read() -> LedgerListProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            page = query_ledger_transaction_list(
                LedgerTransactionListQuery(
                    spec=payload.filter_spec(),
                    group=payload.group,
                    by_group=payload.by_group,
                    limit=payload.limit,
                    offset=payload.offset,
                    sort_by=payload.sort_by,
                    sort_order=payload.sort_order,
                    exclude_llm_rejected=payload.exclude_llm_rejected,
                ),
                bucket_id=bucket_id,
                ports=ports,
            )
            if page.bucket_id != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return LedgerListProjection(
                profile_id=payload.profile_id,
                rows=tuple(
                    LedgerTransactionReviewProjection(
                        transaction=LedgerTransactionProjection.from_payload(
                            ledger_transaction_payload(item.transaction)
                        ),
                        review_status=ledger_transaction_review_status(item.transaction),
                        group_label=item.transaction.group_label,
                    )
                    for item in page.results
                ),
                total=page.total,
                truncated=page.truncated,
                offset=payload.offset,
                limit=payload.limit,
                by_group=payload.by_group,
            )

        return await capture_read_result(context, read, task_name="ledger-list")


def build_ledger_list_definition(ports: LedgerActionPortsFactory) -> OperationDefinition:
    """Register a private-query read without commit or provider authority."""
    return OperationDefinition(
        definition_id=LEDGER_LIST_OPERATION_DEFINITION_ID,
        request_type=LedgerListRequest,
        result_type=LedgerListProjection,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerListRequest,
            executor_type=LedgerListExecutor,
            build=lambda: LedgerListExecutor(ports),
        ),
        phase_codes=(LEDGER_LIST_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_ledger_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Derive period authority from the immutable canonical filter, never caller scope hints."""
    if request.definition_id != LEDGER_LIST_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerListRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    period = request.payload.filter_spec().period
    return resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset({period}) if period is not None else frozenset(),
    )


def build_ledger_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind encrypted selection schemas to canonical period-scope evaluation."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerListProjection,
        access_resolver=resolve_ledger_list_access,
    )
