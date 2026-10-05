"""Registered exact-profile ledger transaction view and decision provenance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.buckets.event import BucketEventType
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..review.filter import LedgerReviewStatus
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .actions_manual import get_manual_transaction, ledger_transaction_result_payload
from .history_query import LedgerHistoryQuery, read_ledger_history
from .id_resolution import resolve_lineage_transaction_id
from .list_query import LLM_DECISION_EVENT_TYPES
from .read_access import resolve_ledger_read_access
from .transaction_projection import LedgerTransactionProjection

LEDGER_VIEW_OPERATION_DEFINITION_ID = "ledger.view"


class LedgerViewRequest(CredentialFreeOperationRequest):
    """An exact profile and a current or superseded transaction handle."""

    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")


class LedgerViewRejectionProjection(BaseModel):
    """The existing notice's decision facts, without a frontend repository read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    occurred_at: datetime
    operator_reason: str


class LedgerViewProjection(BaseModel):
    """Admitted transaction display facts and its latest standing rejection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    latest_llm_rejection: LedgerViewRejectionProjection | None


class LedgerViewExecutor:
    """Read the canonical current transaction and edit-lineage decision facts."""

    def __init__(self, ports: LedgerActionPortsFactory) -> None:
        """Retain only the explicit profile-bound composition capability."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerViewRequest], context: OperationExecutorContext) -> str:
        """Publish an encrypted read result with no domain mutation effect."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_VIEW_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_VIEW_OPERATION_DEFINITION_ID)

        def read() -> LedgerViewProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            selected = resolve_lineage_transaction_id(payload.transaction_prefix, ports.transaction_repository.load())
            result = get_manual_transaction(bucket_id=bucket_id, transaction_id=selected, ports=ports)
            canonical = ledger_transaction_result_payload(result)
            if canonical.bucket_id != bucket_id or canonical.transaction_id != selected:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            history = read_ledger_history(
                LedgerHistoryQuery(transaction_id=selected),
                bucket_id=bucket_id,
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
            )
            decisions = tuple(event for event in history.events if event.event_type in LLM_DECISION_EVENT_TYPES)
            rejection = None
            if decisions and decisions[-1].event_type is BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED:
                latest = decisions[-1]
                rejection = LedgerViewRejectionProjection(
                    occurred_at=latest.occurred_at, operator_reason=latest.payload.get("operator_reason", "")
                )
            return LedgerViewProjection(
                profile_id=payload.profile_id,
                transaction_prefix=payload.transaction_prefix,
                transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
                review_status=canonical.review_status,
                latest_llm_rejection=rejection,
            )

        return await capture_read_result(context, read, task_name="ledger-view")


def build_ledger_view_definition(ports: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare one local read without COMMIT or external-provider capability."""
    return build_single_phase_definition(
        definition_id=LEDGER_VIEW_OPERATION_DEFINITION_ID,
        request_type=LedgerViewRequest,
        result_type=LedgerViewProjection,
        executor_type=LedgerViewExecutor,
        build=lambda: LedgerViewExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_ledger_view_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict result facts and the complete-profile read permission."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerViewProjection,
        access_resolver=resolve_ledger_view_access,
    )


def resolve_ledger_view_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Protect the complete transaction and its cross-period decision lineage."""
    if request.definition_id != LEDGER_VIEW_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerViewRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
