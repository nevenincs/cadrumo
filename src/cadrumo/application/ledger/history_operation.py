"""Encrypted transaction history through the registered profile worker."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.buckets.event import bucket_event_order_key
from ..bucket_event_projection import BucketEventProjection
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .history_query import LedgerHistoryQuery, LedgerHistoryV1, read_ledger_history
from .id_resolution import resolve_lineage_transaction_id

LEDGER_HISTORY_OPERATION_DEFINITION_ID = "ledger.history"


class LedgerHistoryRequest(CredentialFreeOperationRequest):
    """One profile-bound hexadecimal lineage handle and explicit sibling choice."""

    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")
    include_split_siblings: bool = False


class LedgerHistoryProjection(BaseModel):
    """Profile-bound chronological history and its canonical lineage anchors."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")
    include_split_siblings: bool
    transaction_id: Hex64Str
    object_ids: tuple[Hex64Str, ...]
    events: tuple[BucketEventProjection, ...]
    event_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _bound_events(self) -> Self:
        if self.event_count != len(self.events) or any(event.bucket_id != self.profile_id for event in self.events):
            raise ValueError("ledger history events do not match their profile or count")
        if self.transaction_id not in self.object_ids or len(set(self.object_ids)) != len(self.object_ids):
            raise ValueError("ledger history has invalid lineage anchors")
        if tuple(sorted(self.events, key=lambda event: bucket_event_order_key(event.to_event()))) != self.events:
            raise ValueError("ledger history is not in canonical event order")
        return self

    def to_history(self) -> LedgerHistoryV1:
        """Restore the canonical query result for existing CLI rendering."""
        return LedgerHistoryV1(
            bucket_id=str(self.profile_id),
            transaction_id=self.transaction_id,
            object_ids=self.object_ids,
            events=tuple(event.to_event() for event in self.events),
            event_count=self.event_count,
        )


class LedgerHistoryExecutor:
    """Resolve the supplied handle and read its lineage only in worker custody."""

    def __init__(self, ports: LedgerActionPortsFactory) -> None:
        """Retain the ports used for ledger lineage reads."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerHistoryRequest], context: OperationExecutorContext) -> str:
        """Retain canonical history selection and store its encrypted result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_HISTORY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_HISTORY_OPERATION_DEFINITION_ID)

        def read() -> LedgerHistoryProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            selected = resolve_lineage_transaction_id(payload.transaction_prefix, ports.transaction_repository.load())
            history = read_ledger_history(
                LedgerHistoryQuery(transaction_id=selected, include_split_siblings=payload.include_split_siblings),
                bucket_id=bucket_id,
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
            )
            return LedgerHistoryProjection(
                profile_id=payload.profile_id,
                transaction_prefix=payload.transaction_prefix,
                include_split_siblings=payload.include_split_siblings,
                transaction_id=history.transaction_id,
                object_ids=history.object_ids,
                events=tuple(BucketEventProjection.from_event(event) for event in history.events),
                event_count=history.event_count,
            )

        return await capture_read_result(context, read, task_name="ledger-history")


def build_ledger_history_definition(ports: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare a recorded local read without COMMIT or provider effects."""
    return OperationDefinition(
        definition_id=LEDGER_HISTORY_OPERATION_DEFINITION_ID,
        request_type=LedgerHistoryRequest,
        result_type=LedgerHistoryProjection,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerHistoryRequest,
            executor_type=LedgerHistoryExecutor,
            build=lambda: LedgerHistoryExecutor(ports),
        ),
        phase_codes=(LEDGER_HISTORY_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_ledger_history_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the history schemas and its whole-profile lineage disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerHistoryProjection,
        access_resolver=resolve_ledger_history_access,
    )


def resolve_ledger_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require complete-period authority because edit and sibling history span periods."""
    from .read_access import resolve_ledger_read_access

    if request.definition_id != LEDGER_HISTORY_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerHistoryRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
