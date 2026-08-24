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
from ._interactions import OperationActorReference, OperationInteractionId, OperationResponseIntent
from ._models import (
    OperationDefinitionId,
    OperationDiagnosticReference,
    OperationId,
    OperationReference,
    OperationRevision,
)
from ._registry import (
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ._replay import OperationEventCursor, OperationReplayLimit, OperationReplayStatus

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
        terminal = self.lifecycle is OperationLifecycle.TERMINAL
        if terminal != (self.terminal_condition is not None):
            raise ValueError("public terminal lifecycle requires exactly one terminal condition")
        if self.result_ref is not None and self.refusal_ref is not None:
            raise ValueError("public projection cannot expose result and refusal references together")
        if self.terminal_condition is OperationTerminalCondition.SUCCEEDED and self.result_ref is None:
            raise ValueError("successful public projection requires a result reference")
        if self.terminal_condition is OperationTerminalCondition.REFUSED and self.refusal_ref is None:
            raise ValueError("refused public projection requires a refusal reference")
        if not terminal and (self.result_ref is not None or self.refusal_ref is not None):
            raise ValueError("nonterminal public projection cannot expose settlement references")
        if self.progress is not None and (
            self.progress.event_sequence > self.anchor_cursor or self.progress.revision > self.revision
        ):
            raise ValueError("public progress cannot exceed its projection anchor")
        if self.cancellation is OperationCancellation.UNSUPPORTED and self.cancellable_now:
            raise ValueError("unsupported cancellation cannot be currently available")
        if self.cancellation_acknowledged and not self.cancellation_requested:
            raise ValueError("cancellation acknowledgement requires a cancellation request")
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
    outcome_code: OperationEventCode


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
            if self.events or self.next_cursor != self.requested_cursor or self.restart_cursor is not None:
                raise ValueError("caught-up public event page must preserve its cursor")
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
    permitted_intents: frozenset[OperationResponseIntent]

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
    "OperationDetachRefusalCode",
    "OperationDetachRefusalV1",
    "OperationDetachRequestV1",
    "OperationDetachResultV1",
    "OperationDetachSuccessV1",
    "OperationNoPendingInteractionV1",
    "OperationObservationRefusalCode",
    "OperationObservationRefusalV1",
    "OperationObservationRequestV1",
    "OperationObservationResultV1",
    "OperationObservationSuccessV1",
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
    "OperationReviewAvailableInteractionV1",
    "OperationReviewProjectionReferenceV1",
    "OperationReviewProjectionRefusalCode",
    "OperationReviewProjectionRefusalV1",
    "OperationReviewProjectionRequestV1",
    "OperationReviewProjectionResultV1",
    "OperationReviewProjectionSuccessV1",
    "OperationUnsupportedInteractionV1",
    "OperationWorkspaceRefreshTargetRefusalCode",
    "OperationWorkspaceRefreshTargetRefusalV1",
    "OperationWorkspaceRefreshTargetRequestV1",
    "OperationWorkspaceRefreshTargetResultV1",
    "OperationWorkspaceRefreshTargetSuccessV1",
]
