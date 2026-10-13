"""Encrypted transaction history through the registered profile worker.

The history returns each event's payload as the producers wrote it, which can
hold the path an export was written to and the reason a model gave after
reading an attached document. The typed history is a second read of the same
events, with every payload entry the ledger's producers write declared by
name, and with those two left in custody.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.codes import IsoCurrencyCode
from ...core.time.utc import validate_utc_aware
from ...domain.buckets.event import (
    BUCKET_ACTOR_LABEL_MAX_LENGTH,
    BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH,
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    bucket_event_order_key,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..bucket_event_projection import BucketEventProjection
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .history_query import LedgerHistoryQuery, LedgerHistoryV1, read_ledger_history
from .id_resolution import resolve_lineage_transaction_id
from .read_ports import LedgerReadPortsFactory

LEDGER_HISTORY_OPERATION_DEFINITION_ID = "ledger.history"
LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID = "ledger.history.typed"
_DetailValue = Annotated[str, Field(max_length=BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH)]


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


class LedgerHistoryEventDetails(BaseModel):
    """Every payload entry the ledger's event producers write, declared by name.

    Each value is the producer's own text: an identifier, a closed token, a
    count, an amount, a digest, a model stamp, or a reason the person typed.
    A field is absent when the event's kind does not carry it.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    source_command: _DetailValue | None = None
    mutation_kind: _DetailValue | None = None
    direction: _DetailValue | None = None
    amount: _DetailValue | None = None
    currency: IsoCurrencyCode | None = None
    business_pct: _DetailValue | None = None
    usage_ratio_id: _DetailValue | None = None
    prorrata_reference: _DetailValue | None = None
    previous_transaction_id: _DetailValue | None = None
    transaction_id: _DetailValue | None = None
    classification: _DetailValue | None = None
    category_id: _DetailValue | None = None
    category: _DetailValue | None = None
    iva_category: _DetailValue | None = None
    classified_by: _DetailValue | None = None
    provider: _DetailValue | None = None
    provenance: _DetailValue | None = None
    confidence: _DetailValue | None = None
    suggestion_kind: _DetailValue | None = None
    operator_reason: _DetailValue | None = None
    reason: _DetailValue | None = None
    lifecycle_state: _DetailValue | None = None
    previous_lifecycle_state: _DetailValue | None = None
    invoice_id: _DetailValue | None = None
    linked: _DetailValue | None = None
    media_kind: _DetailValue | None = None
    source_sha256: _DetailValue | None = None
    purchase_invoice_evidence_count: _DetailValue | None = None
    attachment_count: _DetailValue | None = None
    cascade_count: _DetailValue | None = None
    import_batch_id: _DetailValue | None = None
    provider_name: _DetailValue | None = None
    source_format: _DetailValue | None = None
    source_row_index: _DetailValue | None = None
    imported_count: _DetailValue | None = None
    skipped_count: _DetailValue | None = None
    split_group_id: _DetailValue | None = None
    parent_transaction_id: _DetailValue | None = None
    merged_transaction_id: _DetailValue | None = None
    child_count: _DetailValue | None = None
    export_format: _DetailValue | None = None
    include_inactive: _DetailValue | None = None
    row_count: _DetailValue | None = None
    byte_size: _DetailValue | None = None
    sha256: _DetailValue | None = None
    transaction_ids_sha256: _DetailValue | None = None
    first_transaction_id: _DetailValue | None = None
    last_transaction_id: _DetailValue | None = None


_DECLARED_DETAIL_NAMES: Final = frozenset(LedgerHistoryEventDetails.model_fields)
_MODEL_REASON_DETAIL: Final = "model_reason"
_OUTPUT_PATH_DETAIL: Final = "output_path"


class LedgerHistoryTypedEvent(BaseModel):
    """One ledger event's declared facts, and a count of what was left in custody.

    The model's reason for a rejected suggestion is not released: the model
    read the attached document, so its reason can quote it. Nor is the path an
    export was written to. An entry no producer is known to write is counted
    and never released.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    event_id: Hex64Str
    event_type: BucketEventType
    occurred_at: datetime
    actor: str = Field(min_length=1, max_length=BUCKET_ACTOR_LABEL_MAX_LENGTH)
    object_type: BucketEventObjectType
    object_id: str = Field(min_length=1, max_length=128)
    details: LedgerHistoryEventDetails
    model_reason_withheld: bool
    output_path_withheld: bool
    undeclared_detail_count: NonNegativeInt

    @field_validator("occurred_at")
    @classmethod
    @pydantic_validation_boundary
    def _occurred_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def from_event(cls, event: BucketEvent) -> Self:
        """Copy the declared entries of one event and account for every other entry."""
        payload = event.payload
        declared = {name: value for name, value in payload.items() if name in _DECLARED_DETAIL_NAMES}
        reduced = {_MODEL_REASON_DETAIL, _OUTPUT_PATH_DETAIL}
        return cls(
            event_id=event.event_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            actor=event.actor,
            object_type=event.object_type,
            object_id=event.object_id,
            details=LedgerHistoryEventDetails.model_validate(declared),
            model_reason_withheld=bool(payload.get(_MODEL_REASON_DETAIL)),
            output_path_withheld=bool(payload.get(_OUTPUT_PATH_DETAIL)),
            undeclared_detail_count=sum(
                1 for name in payload if name not in _DECLARED_DETAIL_NAMES and name not in reduced
            ),
        )


class LedgerHistoryTypedProjection(BaseModel):
    """Profile-bound chronological history in typed form, with its lineage anchors."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")
    include_split_siblings: bool
    transaction_id: Hex64Str
    object_ids: tuple[Hex64Str, ...]
    events: tuple[LedgerHistoryTypedEvent, ...]
    event_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _bound_events(self) -> Self:
        if self.event_count != len(self.events) or len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("typed ledger history events do not match their count or repeat an identity")
        if self.transaction_id not in self.object_ids or len(set(self.object_ids)) != len(self.object_ids):
            raise ValueError("typed ledger history has invalid lineage anchors")
        if tuple(sorted(self.events, key=lambda event: (event.occurred_at, event.event_id))) != self.events:
            raise ValueError("typed ledger history is not in canonical event order")
        return self


def _selected_history(
    ports_factory: LedgerReadPortsFactory, payload: LedgerHistoryRequest, operation: PinnedAuthorityOperation
) -> LedgerHistoryV1:
    """Resolve the lineage handle and read its event chain under the pinned authority."""
    bucket_id = str(payload.profile_id)
    ports = ports_factory(bucket_id=bucket_id, operation=operation)
    if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    catalogue = ports.transaction_repository.load()
    selected = resolve_lineage_transaction_id(payload.transaction_prefix, catalogue)
    return read_ledger_history(
        LedgerHistoryQuery(transaction_id=selected, include_split_siblings=payload.include_split_siblings),
        bucket_id=bucket_id,
        transaction_repository=ports.transaction_repository,
        bucket_event_repository=ports.bucket_event_repository,
        transaction_catalogue=catalogue,
    )


class LedgerHistoryExecutor:
    """Resolve the supplied handle and read its lineage only in worker custody."""

    def __init__(self, ports: LedgerReadPortsFactory) -> None:
        """Retain the ports used for ledger lineage reads."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerHistoryRequest], context: OperationExecutorContext) -> str:
        """Retain canonical history selection and store its encrypted result."""
        payload = request.payload
        if request.definition_id != LEDGER_HISTORY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_HISTORY_OPERATION_DEFINITION_ID)

        def read() -> LedgerHistoryProjection:
            history = _selected_history(self._ports, payload, context.authority_operation)
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


class LedgerHistoryTypedExecutor:
    """Read the same lineage as the history and retain only its declared facts."""

    def __init__(self, ports: LedgerReadPortsFactory) -> None:
        """Retain the ports used for ledger lineage reads."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerHistoryRequest], context: OperationExecutorContext) -> str:
        """Retain canonical history selection and store its typed, encrypted result."""
        payload = request.payload
        if request.definition_id != LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID)

        def read() -> LedgerHistoryTypedProjection:
            # The complete events are read once and stay in worker memory;
            # only their declared entries enter the result operand.
            history = _selected_history(self._ports, payload, context.authority_operation)
            return LedgerHistoryTypedProjection(
                profile_id=payload.profile_id,
                transaction_prefix=payload.transaction_prefix,
                include_split_siblings=payload.include_split_siblings,
                transaction_id=history.transaction_id,
                object_ids=history.object_ids,
                events=tuple(LedgerHistoryTypedEvent.from_event(event) for event in history.events),
                event_count=history.event_count,
            )

        return await capture_read_result(context, read, task_name="ledger-history-typed")


def build_ledger_history_definition(ports: LedgerReadPortsFactory) -> OperationDefinition:
    """Declare a recorded local read without COMMIT or provider effects."""
    return build_single_phase_definition(
        definition_id=LEDGER_HISTORY_OPERATION_DEFINITION_ID,
        request_type=LedgerHistoryRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerHistoryProjection,
        executor_type=LedgerHistoryExecutor,
        build=lambda: LedgerHistoryExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def build_ledger_history_typed_definition(ports: LedgerReadPortsFactory) -> OperationDefinition:
    """Declare the typed read of the same lineage, without COMMIT or provider effects."""
    return build_single_phase_definition(
        definition_id=LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID,
        request_type=LedgerHistoryRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerHistoryTypedProjection,
        executor_type=LedgerHistoryTypedExecutor,
        build=lambda: LedgerHistoryTypedExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def build_ledger_history_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the history schemas and its whole-profile lineage disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerHistoryProjection,
        access_resolver=resolve_ledger_history_access,
    )


def build_ledger_history_typed_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the typed history schemas and the history's whole-profile lineage disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerHistoryTypedProjection,
        access_resolver=resolve_ledger_history_typed_access,
    )


def resolve_ledger_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require complete-period authority because edit and sibling history span periods."""
    return _resolve_history_access(request, context, definition_id=LEDGER_HISTORY_OPERATION_DEFINITION_ID)


def resolve_ledger_history_typed_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Admit the typed history as the history is admitted."""
    return _resolve_history_access(request, context, definition_id=LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID)


def _resolve_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, *, definition_id: str
) -> ResolvedOperationAccess:
    from .read_access import resolve_ledger_read_access

    if request.definition_id != definition_id or not isinstance(request.payload, LedgerHistoryRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
