"""Strict renderer-neutral DTOs for the public operation application boundary."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core import (
    OperationCancellation,
    OperationClosePolicy,
    OperationEffect,
    OperationEventKind,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ...core.identity import ContentDigest
from ...core.time import validate_utc_aware
from ._events import OperationEventCode, OperationEventSequence, OperationLogSeverity
from ._interactions import OperationActorReference, OperationInteractionId
from ._models import (
    OperationDefinitionId,
    OperationDiagnosticReference,
    OperationId,
    OperationReconciliationOutcome,
    OperationReference,
    OperationRevision,
    validate_terminal_reference_meaning,
)
from ._registry import (
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ._replay import OperationEventCursor, OperationReplayLimit, OperationReplayStatus
from ._secret_submission import OperationSecretRequirement

_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class OperationObservationRefusalCode(StrEnum):
    UNSUPPORTED_VERSION = "unsupported_operation_observation_version"
    UNKNOWN_OPERATION = "unknown_operation"
    CURSOR_AHEAD = "cursor_ahead"
    INVALID_CURSOR = "invalid_cursor"
    DEFINITION_CONTRACT_MISMATCH = "definition_contract_mismatch"
    OBSERVATION_UNAVAILABLE = "observation_unavailable"


class OperationReviewProjectionRefusalCode(StrEnum):
    UNSUPPORTED_VERSION = "unsupported_review_projection_version"
    UNKNOWN_OPERATION = "unknown_operation"
    REVIEW_NOT_PENDING = "review_not_pending"
    STALE_REVIEW_REFERENCE = "stale_review_reference"
    REVIEW_EXPIRED = "review_expired"
    DEFINITION_CONTRACT_MISMATCH = "definition_contract_mismatch"
    REVIEW_SCHEMA_MISMATCH = "review_schema_mismatch"
    REVIEW_PROJECTION_UNAVAILABLE = "review_projection_unavailable"


class OperationWorkspaceRefreshTargetRefusalCode(StrEnum):
    UNSUPPORTED_VERSION = "unsupported_refresh_target_version"
    UNKNOWN_OPERATION = "unknown_operation"
    OPERATION_NOT_TERMINAL = "operation_not_terminal"
    OPERATION_NOT_SUCCESSFUL = "operation_not_successful"
    REFRESH_ADAPTER_UNAVAILABLE = "refresh_adapter_unavailable"
    DEFINITION_CONTRACT_MISMATCH = "definition_contract_mismatch"
    REFRESH_SCHEMA_MISMATCH = "refresh_schema_mismatch"
    UNSAFE_REFRESH_TARGET = "unsafe_refresh_target"


class OperationResponseControlRefusalCode(StrEnum):
    UNSUPPORTED_VERSION = "unsupported_response_control_version"
    UNKNOWN_OPERATION = "unknown_operation"
    RESPONSE_NOT_PENDING = "response_not_pending"
    STALE_OPERATION_REVISION = "stale_operation_revision"
    RESPONSE_AUTHORITY_UNAVAILABLE = "response_authority_unavailable"


class OperationCancellationRefusalCode(StrEnum):
    UNSUPPORTED_VERSION = "unsupported_cancellation_version"
    UNKNOWN_OPERATION = "unknown_operation"
    STALE_OPERATION_REVISION = "stale_operation_revision"
    OPERATION_TERMINAL = "operation_terminal"
    CANCELLATION_UNSUPPORTED = "cancellation_unsupported"
    CANCELLATION_UNAVAILABLE = "cancellation_unavailable"


class OperationDetachRefusalCode(StrEnum):
    UNSUPPORTED_VERSION = "unsupported_detach_version"
    UNKNOWN_OPERATION = "unknown_operation"
    STALE_OPERATION_REVISION = "stale_operation_revision"
    DETACH_NOT_ALLOWED = "detach_not_allowed"


class OperationObservationVersionHeader(BaseModel):
    """Minimal header parsed before exact observation request dispatch."""

    model_config = _PUBLIC_CONFIG
    observation_version: Annotated[int, Field(ge=1)]


class OperationReviewProjectionVersionHeader(BaseModel):
    """Minimal header parsed before exact REVIEW request dispatch."""

    model_config = _PUBLIC_CONFIG
    review_projection_version: Annotated[int, Field(ge=1)]


class OperationResponseControlVersionHeader(BaseModel):
    """Minimal header parsed before exact response-control request dispatch."""

    model_config = _PUBLIC_CONFIG
    response_control_version: Annotated[int, Field(ge=1)]


class OperationCancellationVersionHeader(BaseModel):
    """Minimal header parsed before exact cancellation request dispatch."""

    model_config = _PUBLIC_CONFIG
    cancellation_version: Annotated[int, Field(ge=1)]


class OperationDetachVersionHeader(BaseModel):
    """Minimal header parsed before exact detach request dispatch."""

    model_config = _PUBLIC_CONFIG
    detach_version: Annotated[int, Field(ge=1)]


class OperationWorkspaceRefreshTargetVersionHeader(BaseModel):
    """Minimal header parsed before exact refresh-target request dispatch."""

    model_config = _PUBLIC_CONFIG
    refresh_target_version: Annotated[int, Field(ge=1)]


class OperationObservationRequestV1(BaseModel):
    """Request one atomic projection and bounded event page."""

    model_config = _PUBLIC_CONFIG

    observation_version: Literal[1] = 1
    operation_id: OperationId
    after_cursor: OperationEventCursor
    page_limit: OperationReplayLimit


class OperationPublicProgressV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    completed: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(gt=0)]
    unit_code: OperationEventCode | None
    phase_code: OperationEventCode | None
    event_sequence: OperationEventSequence
    revision: OperationRevision

    @model_validator(mode="after")
    def _validate_progress(self) -> OperationPublicProgressV1:
        if self.completed > self.total:
            raise ValueError("public operation progress cannot exceed its total")
        return self


class OperationNoPendingInteractionV1(BaseModel):
    model_config = _PUBLIC_CONFIG
    disposition: Literal["none"] = "none"


class OperationReviewProjectionReferenceV1(BaseModel):
    """Safe REVIEW identity; deliberately excludes every response credential."""

    model_config = _PUBLIC_CONFIG

    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: OperationRevision
    review_projection_schema: OperationSchemaIdentityV1
    definition_contract_digest: ContentDigest
    expires_at: datetime | None

    @model_validator(mode="after")
    def _validate_expiry(self) -> OperationReviewProjectionReferenceV1:
        if self.expires_at is not None:
            validate_utc_aware(self.expires_at)
        return self


class OperationReviewAvailableInteractionV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    disposition: Literal["review_available"] = "review_available"
    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: OperationRevision
    presentation_code: OperationEventCode
    response_schema: OperationSchemaIdentityV1
    expires_at: datetime | None
    review_reference: OperationReviewProjectionReferenceV1

    @model_validator(mode="after")
    def _validate_reference(self) -> OperationReviewAvailableInteractionV1:
        if self.expires_at is not None:
            validate_utc_aware(self.expires_at)
        reference = self.review_reference
        if (reference.operation_id, reference.interaction_id, reference.revision, reference.expires_at) != (
            self.operation_id,
            self.interaction_id,
            self.revision,
            self.expires_at,
        ):
            raise ValueError("public REVIEW interaction does not match its safe reference")
        return self


class OperationUnsupportedInteractionV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    disposition: Literal["unsupported"] = "unsupported"
    interaction_kind: Literal[OperationInteractionKind.INPUT, OperationInteractionKind.CHOICE]
    interaction_id: OperationInteractionId
    revision: OperationRevision
    presentation_code: OperationEventCode
    unsupported_code: OperationEventCode
    expires_at: datetime | None

    @model_validator(mode="after")
    def _validate_expiry(self) -> OperationUnsupportedInteractionV1:
        if self.expires_at is not None:
            validate_utc_aware(self.expires_at)
        return self


OperationPublicPendingInteractionV1 = Annotated[
    OperationNoPendingInteractionV1 | OperationReviewAvailableInteractionV1 | OperationUnsupportedInteractionV1,
    Field(discriminator="disposition"),
]


class OperationPublicProjectionV1(BaseModel):
    """Current anchored operation state with no persistence or frontend types."""

    model_config = _PUBLIC_CONFIG

    observation_version: Literal[1] = 1
    operation_id: OperationId
    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    revision: OperationRevision
    anchor_cursor: OperationEventCursor
    definition_contract: OperationPublicDefinitionContractV1
    contract_set_digest: ContentDigest
    lifecycle: OperationLifecycle
    terminal_condition: OperationTerminalCondition | None
    effect: OperationEffect
    phase_code: OperationEventCode | None
    started_at: datetime | None
    updated_at: datetime
    progress: OperationPublicProgressV1 | None
    close_policy: OperationClosePolicy
    cancellation: OperationCancellation
    cancellable_now: bool
    cancellation_requested: bool
    cancellation_acknowledged: bool
    execution_deadline_at: datetime | None
    cleanup_deadline_at: datetime | None
    pending_interaction: OperationPublicPendingInteractionV1
    result_ref: OperationReference | None
    refusal_ref: OperationReference | None
    diagnostic_ref: OperationDiagnosticReference | None

    @model_validator(mode="after")
    def _validate_projection(self) -> OperationPublicProjectionV1:
        for value in (self.started_at, self.execution_deadline_at, self.cleanup_deadline_at):
            if value is not None:
                validate_utc_aware(value)
        validate_utc_aware(self.updated_at)
        if self.definition_contract.definition_id != self.definition_id:
            raise ValueError("public projection definition does not match its contract")
        if self.close_policy is not self.definition_contract.close_policy:
            raise ValueError("public projection close policy does not match its definition contract")
        if self.cancellation is not self.definition_contract.cancellation:
            raise ValueError("public projection cancellation does not match its definition contract")
        if self.started_at is not None and self.started_at > self.updated_at:
            raise ValueError("public operation start cannot follow its last update")
        if (
            self.started_at is not None
            and self.execution_deadline_at is not None
            and self.execution_deadline_at < self.started_at
        ):
            raise ValueError("public execution deadline cannot precede operation start")
        if (
            self.started_at is not None
            and self.cleanup_deadline_at is not None
            and self.cleanup_deadline_at < self.started_at
        ):
            raise ValueError("public cleanup deadline cannot precede operation start")
        terminal = self.lifecycle is OperationLifecycle.TERMINAL
        if terminal != (self.terminal_condition is not None):
            raise ValueError("public terminal lifecycle requires exactly one terminal condition")
        if terminal and not isinstance(self.pending_interaction, OperationNoPendingInteractionV1):
            raise ValueError("public terminal projection cannot carry a pending interaction")
        if terminal and self.cancellable_now:
            raise ValueError("public terminal projection cannot remain cancellable")
        pending = self.pending_interaction
        if not isinstance(pending, OperationNoPendingInteractionV1):
            if self.lifecycle is not OperationLifecycle.WAITING_FOR_INTERACTION:
                raise ValueError("public pending interaction requires waiting-for-interaction lifecycle")
            if pending.revision != self.revision:
                raise ValueError("public pending interaction does not match the current operation revision")
            interaction_kind = (
                OperationInteractionKind.REVIEW
                if isinstance(pending, OperationReviewAvailableInteractionV1)
                else pending.interaction_kind
            )
            if interaction_kind not in self.definition_contract.interaction_kinds:
                raise ValueError("public pending interaction kind is not declared by the definition contract")
        if isinstance(pending, OperationReviewAvailableInteractionV1):
            contract = self.definition_contract
            if pending.operation_id != self.operation_id:
                raise ValueError("public REVIEW interaction does not match the current operation")
            if pending.review_reference.definition_contract_digest != contract.definition_contract_digest:
                raise ValueError("public REVIEW reference does not match the current definition contract")
            if pending.review_reference.review_projection_schema != contract.review_projection_schema:
                raise ValueError("public REVIEW reference does not match the registered projection schema")
            if pending.response_schema != contract.interaction_response_schema:
                raise ValueError("public REVIEW interaction does not match the registered response schema")
        if self.result_ref is not None and self.refusal_ref is not None:
            raise ValueError("public projection cannot expose result and refusal references together")
        if self.terminal_condition is OperationTerminalCondition.SUCCEEDED and self.result_ref is None:
            raise ValueError("successful public projection requires a result reference")
        if self.terminal_condition is OperationTerminalCondition.REFUSED and self.refusal_ref is None:
            raise ValueError("refused public projection requires a refusal reference")
        if not terminal and (self.result_ref is not None or self.refusal_ref is not None):
            raise ValueError("nonterminal public projection cannot expose settlement references")
        if self.progress is not None:
            if self.progress.event_sequence > self.anchor_cursor or self.progress.revision > self.revision:
                raise ValueError("public progress cannot exceed its projection anchor")
            if self.progress.phase_code != self.phase_code:
                raise ValueError("public progress phase must match the current projection phase")
        if self.cancellation is OperationCancellation.UNSUPPORTED and self.cancellable_now:
            raise ValueError("unsupported cancellation cannot be currently available")
        if self.cancellable_now and (self.cancellation_requested or self.cancellation_acknowledged):
            raise ValueError("public cancellation cannot remain currently available after it is requested")
        if self.cancellable_now and self.lifecycle is OperationLifecycle.SETTLING:
            raise ValueError("public cancellation cannot be currently available while settlement is underway")
        if self.cancellation is OperationCancellation.UNSUPPORTED and (
            self.cancellation_requested or self.cancellation_acknowledged
        ):
            raise ValueError("unsupported cancellation cannot carry request or acknowledgement facts")
        if self.cancellation_requested != (self.cleanup_deadline_at is not None):
            raise ValueError("public cleanup deadline and cancellation request must be declared together")
        if self.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED and not self.cancellation_requested:
            raise ValueError("cancellation-requested lifecycle requires its declared request fact")
        if self.cancellation_requested and self.lifecycle in {
            OperationLifecycle.CREATED,
            OperationLifecycle.QUEUED,
            OperationLifecycle.RUNNING,
            OperationLifecycle.WAITING_FOR_INTERACTION,
            OperationLifecycle.WAITING_FOR_EXTERNAL,
        }:
            raise ValueError("public cancellation request disagrees with the current lifecycle")
        if self.cancellation_acknowledged and not self.cancellation_requested:
            raise ValueError("cancellation acknowledgement requires a cancellation request")
        if self.cancellation_acknowledged and self.lifecycle not in {
            OperationLifecycle.SETTLING,
            OperationLifecycle.TERMINAL,
        }:
            raise ValueError("cancellation acknowledgement requires settling or terminal lifecycle")
        if self.terminal_condition is OperationTerminalCondition.CANCELLED and not self.cancellation_acknowledged:
            raise ValueError("cancelled public operation requires cancellation acknowledgement")
        return self


class _OperationPublicEventBase(BaseModel):
    model_config = _PUBLIC_CONFIG

    revision: OperationRevision
    sequence: OperationEventSequence
    timestamp: datetime
    code: OperationEventCode

    @model_validator(mode="after")
    def _validate_timestamp(self) -> _OperationPublicEventBase:
        validate_utc_aware(self.timestamp)
        return self


class OperationPublicPhaseEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.PHASE] = OperationEventKind.PHASE
    phase_code: OperationEventCode


class OperationPublicProgressEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.PROGRESS] = OperationEventKind.PROGRESS
    completed: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(gt=0)]
    unit_code: OperationEventCode | None

    @model_validator(mode="after")
    def _validate_progress(self) -> OperationPublicProgressEventV1:
        if self.completed > self.total:
            raise ValueError("public progress event cannot exceed its total")
        return self


class OperationPublicLogEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.LOG] = OperationEventKind.LOG
    severity: OperationLogSeverity
    diagnostic_ref: OperationDiagnosticReference | None


class OperationPublicEffectEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.EFFECT] = OperationEventKind.EFFECT
    effect: OperationEffect


class OperationPublicNoticeEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.NOTICE] = OperationEventKind.NOTICE
    notice_code: OperationEventCode


class OperationPublicReconciliationEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.RECONCILIATION] = OperationEventKind.RECONCILIATION
    outcome: OperationReconciliationOutcome


class OperationPublicDiagnosticEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.DIAGNOSTIC] = OperationEventKind.DIAGNOSTIC
    diagnostic_ref: OperationDiagnosticReference


class OperationPublicInteractionEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.INTERACTION] = OperationEventKind.INTERACTION
    interaction_id: OperationInteractionId


class OperationPublicTerminalEventV1(_OperationPublicEventBase):
    kind: Literal[OperationEventKind.TERMINAL] = OperationEventKind.TERMINAL
    condition: OperationTerminalCondition
    effect: OperationEffect
    result_ref: OperationReference | None
    refusal_ref: OperationReference | None
    diagnostic_ref: OperationDiagnosticReference | None

    @model_validator(mode="after")
    def _validate_settlement_references(self) -> OperationPublicTerminalEventV1:
        validate_terminal_reference_meaning(
            condition=self.condition,
            result_ref=self.result_ref,
            refusal_ref=self.refusal_ref,
        )
        return self


OperationPublicEventV1 = Annotated[
    OperationPublicPhaseEventV1
    | OperationPublicProgressEventV1
    | OperationPublicLogEventV1
    | OperationPublicEffectEventV1
    | OperationPublicNoticeEventV1
    | OperationPublicReconciliationEventV1
    | OperationPublicDiagnosticEventV1
    | OperationPublicInteractionEventV1
    | OperationPublicTerminalEventV1,
    Field(discriminator="kind"),
]


class OperationPublicEventPageV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    observation_version: Literal[1] = 1
    operation_id: OperationId
    anchor_cursor: OperationEventCursor
    requested_cursor: OperationEventCursor
    status: Literal[
        OperationReplayStatus.PAGE,
        OperationReplayStatus.CAUGHT_UP,
        OperationReplayStatus.EXPIRED,
        OperationReplayStatus.COMPACTED,
    ]
    events: tuple[OperationPublicEventV1, ...]
    next_cursor: OperationEventCursor
    restart_cursor: OperationEventCursor | None

    @model_validator(mode="after")
    def _validate_page(self) -> OperationPublicEventPageV1:
        if self.requested_cursor > self.anchor_cursor:
            raise ValueError("public event-page cursor cannot exceed its anchor")
        if self.status is OperationReplayStatus.PAGE:
            if not self.events:
                raise ValueError("public event page requires at least one event")
            sequences = tuple(event.sequence for event in self.events)
            if sequences[0] != self.requested_cursor + 1 or any(
                current != previous + 1 for previous, current in pairwise(sequences)
            ):
                raise ValueError("public event page must be contiguous after the requested cursor")
            if self.next_cursor != sequences[-1] or self.restart_cursor is not None:
                raise ValueError("public event page cursor does not match its final row")
        elif self.status is OperationReplayStatus.CAUGHT_UP:
            if (
                self.events
                or self.requested_cursor != self.anchor_cursor
                or self.next_cursor != self.anchor_cursor
                or self.restart_cursor is not None
            ):
                raise ValueError("caught-up public event page must equal its observation anchor cursor")
        else:
            if self.events or self.restart_cursor is None or self.next_cursor != self.restart_cursor:
                raise ValueError("resynchronizing public event page requires one restart cursor and no rows")
            if self.restart_cursor <= self.requested_cursor:
                raise ValueError("public restart cursor must advance beyond the requested cursor")
        if self.next_cursor > self.anchor_cursor or any(event.sequence > self.anchor_cursor for event in self.events):
            raise ValueError("public event rows cannot exceed their observation anchor")
        return self


class OperationObservationSuccessV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    observation_version: Literal[1] = 1
    projection: OperationPublicProjectionV1
    event_page: OperationPublicEventPageV1

    @model_validator(mode="after")
    def _validate_anchor(self) -> OperationObservationSuccessV1:
        if (self.projection.operation_id, self.projection.anchor_cursor) != (
            self.event_page.operation_id,
            self.event_page.anchor_cursor,
        ):
            raise ValueError("public observation projection and event page must share one anchor")
        if any(event.revision > self.projection.revision for event in self.event_page.events):
            raise ValueError("public event row revision cannot exceed its projection revision")
        return self


class OperationObservationRefusalV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    observation_version: Literal[1] = 1
    code: OperationObservationRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


OperationObservationResultV1 = Annotated[
    OperationObservationSuccessV1 | OperationObservationRefusalV1,
    Field(discriminator="outcome"),
]


class OperationReviewProjectionRequestV1(BaseModel):
    model_config = _PUBLIC_CONFIG
    review_projection_version: Literal[1] = 1
    reference: OperationReviewProjectionReferenceV1


class OperationReviewProjectionSuccessV1[ReviewProjectionT: BaseModel](BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    review_projection_version: Literal[1] = 1
    projection_schema: OperationSchemaIdentityV1
    definition_contract_digest: ContentDigest
    projection: ReviewProjectionT


class OperationReviewProjectionRefusalV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    review_projection_version: Literal[1] = 1
    code: OperationReviewProjectionRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


type OperationReviewProjectionResultV1[ReviewProjectionT: BaseModel] = Annotated[
    OperationReviewProjectionSuccessV1[ReviewProjectionT] | OperationReviewProjectionRefusalV1,
    Field(discriminator="outcome"),
]


class OperationResponseControlRequestV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    response_control_version: Literal[1] = 1
    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: OperationRevision
    actor_ref: OperationActorReference


class OperationResponseControlSuccessV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    response_control_version: Literal[1] = 1
    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: OperationRevision
    available: bool
    permitted_intents: frozenset[Literal["apply", "reject"]]

    @model_validator(mode="after")
    def _validate_availability(self) -> OperationResponseControlSuccessV1:
        if self.available != bool(self.permitted_intents):
            raise ValueError("response-control availability must match its permitted intents")
        return self


class OperationResponseControlRefusalV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    response_control_version: Literal[1] = 1
    code: OperationResponseControlRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


OperationResponseControlResultV1 = Annotated[
    OperationResponseControlSuccessV1 | OperationResponseControlRefusalV1,
    Field(discriminator="outcome"),
]


class OperationResponseApplyRequestV1(OperationResponseControlRequestV1):
    """Apply one exact pending REVIEW through separately held authority."""

    response_action: Literal["apply"] = "apply"
    responded_at: datetime

    @model_validator(mode="after")
    def _validate_response_time(self) -> OperationResponseApplyRequestV1:
        validate_utc_aware(self.responded_at)
        return self


class OperationResponseRejectRequestV1(OperationResponseControlRequestV1):
    """Reject one exact pending REVIEW through separately held authority."""

    response_action: Literal["reject"] = "reject"
    responded_at: datetime
    reason_code: OperationEventCode | None = None

    @model_validator(mode="after")
    def _validate_response_time(self) -> OperationResponseRejectRequestV1:
        validate_utc_aware(self.responded_at)
        return self


OperationResponseMutationRequestV1 = Annotated[
    OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1,
    Field(discriminator="response_action"),
]


class OperationResponseMutationSuccessV1(BaseModel):
    """Safe acknowledgement that one exact response was durably consumed."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    response_control_version: Literal[1] = 1
    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: OperationRevision
    response_action: Literal["apply", "reject"]


OperationResponseMutationResultV1 = Annotated[
    OperationResponseMutationSuccessV1 | OperationResponseControlRefusalV1,
    Field(discriminator="outcome"),
]


class OperationSubmissionReceiptV1(BaseModel):
    """Credential-free result of durable registered-operation submission."""

    model_config = _PUBLIC_CONFIG

    submission_version: Literal[1] = 1
    operation_id: OperationId
    secret_requirement: OperationSecretRequirement | None


class OperationCancellationRequestV1(BaseModel):
    model_config = _PUBLIC_CONFIG
    cancellation_version: Literal[1] = 1
    operation_id: OperationId
    expected_revision: OperationRevision


class OperationCancellationSuccessV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    cancellation_version: Literal[1] = 1
    operation_id: OperationId
    revision: OperationRevision
    cancellation_requested: Literal[True] = True
    cancellation_acknowledged: bool


class OperationCancellationRefusalV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    cancellation_version: Literal[1] = 1
    code: OperationCancellationRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


OperationCancellationResultV1 = Annotated[
    OperationCancellationSuccessV1 | OperationCancellationRefusalV1,
    Field(discriminator="outcome"),
]


class OperationDetachRequestV1(BaseModel):
    model_config = _PUBLIC_CONFIG
    detach_version: Literal[1] = 1
    operation_id: OperationId
    expected_revision: OperationRevision


class OperationDetachSuccessV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    detach_version: Literal[1] = 1
    operation_id: OperationId
    revision: OperationRevision
    detached: Literal[True] = True


class OperationDetachRefusalV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    detach_version: Literal[1] = 1
    code: OperationDetachRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


OperationDetachResultV1 = Annotated[
    OperationDetachSuccessV1 | OperationDetachRefusalV1,
    Field(discriminator="outcome"),
]


class OperationWorkspaceRefreshTargetRequestV1(BaseModel):
    """Resolve a restart-safe target without accepting a caller result reference."""

    model_config = _PUBLIC_CONFIG

    refresh_target_version: Literal[1] = 1
    operation_id: OperationId
    terminal_revision: OperationRevision
    definition_contract_digest: ContentDigest
    target_schema: OperationSchemaIdentityV1


class OperationWorkspaceRefreshTargetSuccessV1[RefreshTargetT: BaseModel](BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    refresh_target_version: Literal[1] = 1
    target_schema: OperationSchemaIdentityV1
    definition_contract_digest: ContentDigest
    target: RefreshTargetT


class OperationWorkspaceRefreshTargetRefusalV1(BaseModel):
    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    refresh_target_version: Literal[1] = 1
    code: OperationWorkspaceRefreshTargetRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


type OperationWorkspaceRefreshTargetResultV1[RefreshTargetT: BaseModel] = Annotated[
    OperationWorkspaceRefreshTargetSuccessV1[RefreshTargetT] | OperationWorkspaceRefreshTargetRefusalV1,
    Field(discriminator="outcome"),
]


__all__ = [
    "OperationCancellationRefusalCode",
    "OperationCancellationRefusalV1",
    "OperationCancellationRequestV1",
    "OperationCancellationResultV1",
    "OperationCancellationSuccessV1",
    "OperationCancellationVersionHeader",
    "OperationDetachRefusalCode",
    "OperationDetachRefusalV1",
    "OperationDetachRequestV1",
    "OperationDetachResultV1",
    "OperationDetachSuccessV1",
    "OperationDetachVersionHeader",
    "OperationNoPendingInteractionV1",
    "OperationObservationRefusalCode",
    "OperationObservationRefusalV1",
    "OperationObservationRequestV1",
    "OperationObservationResultV1",
    "OperationObservationSuccessV1",
    "OperationObservationVersionHeader",
    "OperationPublicDiagnosticEventV1",
    "OperationPublicEffectEventV1",
    "OperationPublicEventPageV1",
    "OperationPublicEventV1",
    "OperationPublicInteractionEventV1",
    "OperationPublicLogEventV1",
    "OperationPublicNoticeEventV1",
    "OperationPublicPendingInteractionV1",
    "OperationPublicPhaseEventV1",
    "OperationPublicProgressEventV1",
    "OperationPublicProgressV1",
    "OperationPublicProjectionV1",
    "OperationPublicReconciliationEventV1",
    "OperationPublicTerminalEventV1",
    "OperationResponseControlRefusalCode",
    "OperationResponseControlRefusalV1",
    "OperationResponseControlRequestV1",
    "OperationResponseControlResultV1",
    "OperationResponseControlSuccessV1",
    "OperationResponseControlVersionHeader",
    "OperationResponseApplyRequestV1",
    "OperationResponseMutationRequestV1",
    "OperationResponseMutationResultV1",
    "OperationResponseMutationSuccessV1",
    "OperationResponseRejectRequestV1",
    "OperationReviewAvailableInteractionV1",
    "OperationReviewProjectionReferenceV1",
    "OperationReviewProjectionRefusalCode",
    "OperationReviewProjectionRefusalV1",
    "OperationReviewProjectionRequestV1",
    "OperationReviewProjectionResultV1",
    "OperationReviewProjectionSuccessV1",
    "OperationReviewProjectionVersionHeader",
    "OperationSubmissionReceiptV1",
    "OperationUnsupportedInteractionV1",
    "OperationWorkspaceRefreshTargetRefusalCode",
    "OperationWorkspaceRefreshTargetRefusalV1",
    "OperationWorkspaceRefreshTargetRequestV1",
    "OperationWorkspaceRefreshTargetResultV1",
    "OperationWorkspaceRefreshTargetSuccessV1",
    "OperationWorkspaceRefreshTargetVersionHeader",
]
