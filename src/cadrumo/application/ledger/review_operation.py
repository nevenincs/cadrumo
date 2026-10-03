"""Encrypted canonical ledger review through exact-profile worker custody."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.transaction_ids import TransactionId
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
from ..review.filter import LedgerReviewFilterSpec, LedgerReviewStatus
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .actions_manual import query_ledger_review_rows
from .id_resolution import resolve_lineage_transaction_id
from .read_access import resolve_ledger_read_access
from .review_filter import ledger_review_query_for_spec
from .transaction_projection import LedgerTransactionProjection

LEDGER_REVIEW_OPERATION_DEFINITION_ID = "ledger.review"


class LedgerReviewRequest(BaseModel):
    """Private review filters and an optional stable transaction handle."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    filters: tuple[str, ...] = ()
    transaction_prefix: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")

    def filter_spec(self) -> LedgerReviewFilterSpec:
        """Resolve authority and execution through the same canonical grammar."""
        try:
            return LedgerReviewFilterSpec.from_strings(self.filters)
        except FilterParseError:
            raise ValueError("invalid ledger review filters") from None

    @model_validator(mode="after")
    def valid_filters(self) -> LedgerReviewRequest:
        """Keep private filter values out of validation diagnostics."""
        self.filter_spec()
        return self


class LedgerReviewRowProjection(BaseModel):
    """The canonical review row, with transaction facts only for a detail query."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    id: TransactionId
    date: str
    amount: str
    description: str
    status: LedgerReviewStatus
    transaction: LedgerTransactionProjection | None = None


class LedgerReviewProjection(BaseModel):
    """Canonical ordered review rows and their exact displayed filter labels."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_prefix: str | None
    rows: tuple[LedgerReviewRowProjection, ...]
    filters: tuple[str, ...]

    @model_validator(mode="after")
    def consistent_detail(self) -> LedgerReviewProjection:
        """Refuse a mixed list/detail projection or inconsistent transaction identity."""
        detail = self.transaction_prefix is not None
        if detail and len(self.rows) > 1:
            raise ValueError("ledger review detail contains multiple rows")
        for row in self.rows:
            if detail != (row.transaction is not None):
                raise ValueError("ledger review detail facts disagree with selection")
            if row.transaction is not None and row.transaction.transaction_id != row.id:
                raise ValueError("ledger review row and transaction identities disagree")
        return self


class LedgerReviewExecutor:
    """Run the existing review query wholly inside retained profile custody."""

    def __init__(self, ports: LedgerActionPortsFactory) -> None:
        """Retain explicit exact-profile repository composition."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerReviewRequest], context: OperationExecutorContext) -> str:
        """Publish the canonical read result without domain mutation."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_REVIEW_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_REVIEW_OPERATION_DEFINITION_ID)

        def read() -> LedgerReviewProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            catalogue = ports.transaction_repository.load()
            selected = (
                resolve_lineage_transaction_id(payload.transaction_prefix, catalogue)
                if payload.transaction_prefix is not None
                else None
            )
            result = query_ledger_review_rows(
                ledger_review_query_for_spec(payload.filter_spec(), bucket_id=bucket_id, transaction_id=selected),
                ports=ports,
                catalogue=catalogue,
            )
            if result.bucket_id != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return LedgerReviewProjection(
                profile_id=payload.profile_id,
                transaction_prefix=payload.transaction_prefix,
                rows=tuple(LedgerReviewRowProjection.model_validate_json(row.model_dump_json()) for row in result.rows),
                filters=result.filters,
            )

        return await capture_read_result(context, read, task_name="ledger-review")


def build_ledger_review_definition(ports: LedgerActionPortsFactory) -> OperationDefinition:
    """Register private review input and output with no mutation permission."""
    return OperationDefinition(
        definition_id=LEDGER_REVIEW_OPERATION_DEFINITION_ID,
        request_type=LedgerReviewRequest,
        result_type=LedgerReviewProjection,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerReviewRequest,
            executor_type=LedgerReviewExecutor,
            build=lambda: LedgerReviewExecutor(ports),
        ),
        phase_codes=(LEDGER_REVIEW_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_ledger_review_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Derive review disclosure from immutable canonical period clauses."""
    if request.definition_id != LEDGER_REVIEW_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerReviewRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    period = request.payload.filter_spec().period
    return resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset({period}) if period is not None else frozenset(),
    )


def build_ledger_review_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind encrypted review rows and period-scoped disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerReviewProjection,
        access_resolver=resolve_ledger_review_access,
    )
