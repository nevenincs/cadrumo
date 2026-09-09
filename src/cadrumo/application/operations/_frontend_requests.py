"""Renderer-neutral operation request, response, refusal, and event contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ...core.identity import ContentDigest
from ...core.operations import OperationEffect, OperationEventKind, OperationTerminalCondition
from ...core.time.utc import validate_utc_aware
from ._frontend_projection import OperationPublicProjectionV1, OperationReviewProjectionReferenceV1
from .event_replay import OperationEventCursor
from .events import OperationEventCode, OperationEventSequence, OperationLogSeverity
from .interactions import OperationActorReference, OperationInteractionId, OperationResponseIntentValue
from .models import (
    OperationDiagnosticReference,
    OperationId,
    OperationReconciliationOutcome,
    OperationReference,
    OperationRevision,
    validate_terminal_reference_meaning,
)
from .persistence.replay import (
    RESYNCHRONIZING_REPLAY_STATUSES,
    OperationReplayLimit,
    OperationReplayStatus,
    PublicReplayStatus,
)
from .registry import OperationSchemaIdentityV1
from .secret_submission import OperationSecretRequirement

_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class OperationObservationRefusalCode(StrEnum):
    """Stable refusal codes for operation observation requests."""

    UNSUPPORTED_VERSION = "unsupported_operation_observation_version"
    UNKNOWN_OPERATION = "unknown_operation"
    CURSOR_AHEAD = "cursor_ahead"
    INVALID_CURSOR = "invalid_cursor"
    DEFINITION_CONTRACT_MISMATCH = "definition_contract_mismatch"
    OBSERVATION_UNAVAILABLE = "observation_unavailable"


class OperationReviewProjectionRefusalCode(StrEnum):
    """Stable refusal codes for REVIEW projection requests."""

    UNSUPPORTED_VERSION = "unsupported_review_projection_version"
    UNKNOWN_OPERATION = "unknown_operation"
    REVIEW_NOT_PENDING = "review_not_pending"
    STALE_REVIEW_REFERENCE = "stale_review_reference"
    REVIEW_EXPIRED = "review_expired"
    DEFINITION_CONTRACT_MISMATCH = "definition_contract_mismatch"
    REVIEW_SCHEMA_MISMATCH = "review_schema_mismatch"
    REVIEW_PROJECTION_UNAVAILABLE = "review_projection_unavailable"


class OperationResultProjectionRefusalCode(StrEnum):
    """Stable refusal codes for settled-result projection requests."""

    UNSUPPORTED_VERSION = "unsupported_result_projection_version"
    UNKNOWN_OPERATION = "unknown_operation"
    OPERATION_NOT_TERMINAL = "operation_not_terminal"
    OPERATION_NOT_SUCCESSFUL = "operation_not_successful"
    STALE_OPERATION_REVISION = "stale_operation_revision"
    DEFINITION_CONTRACT_MISMATCH = "definition_contract_mismatch"
    RESULT_SCHEMA_MISMATCH = "result_schema_mismatch"
    RESULT_PROJECTION_UNAVAILABLE = "result_projection_unavailable"


class OperationWorkspaceRefreshTargetRefusalCode(StrEnum):
    """Stable refusal codes for workspace refresh-target requests."""

    UNSUPPORTED_VERSION = "unsupported_refresh_target_version"
    UNKNOWN_OPERATION = "unknown_operation"
    OPERATION_NOT_TERMINAL = "operation_not_terminal"
    OPERATION_NOT_SUCCESSFUL = "operation_not_successful"
    REFRESH_ADAPTER_UNAVAILABLE = "refresh_adapter_unavailable"
    DEFINITION_CONTRACT_MISMATCH = "definition_contract_mismatch"
    REFRESH_SCHEMA_MISMATCH = "refresh_schema_mismatch"
    UNSAFE_REFRESH_TARGET = "unsafe_refresh_target"


class OperationResponseControlRefusalCode(StrEnum):
    """Stable refusal codes for response-control requests."""

    UNSUPPORTED_VERSION = "unsupported_response_control_version"
    UNKNOWN_OPERATION = "unknown_operation"
    RESPONSE_NOT_PENDING = "response_not_pending"
    STALE_OPERATION_REVISION = "stale_operation_revision"
    RESPONSE_AUTHORITY_UNAVAILABLE = "response_authority_unavailable"


class OperationCancellationRefusalCode(StrEnum):
    """Stable refusal codes for cancellation requests."""

    UNSUPPORTED_VERSION = "unsupported_cancellation_version"
    UNKNOWN_OPERATION = "unknown_operation"
    STALE_OPERATION_REVISION = "stale_operation_revision"
    OPERATION_TERMINAL = "operation_terminal"
    CANCELLATION_UNSUPPORTED = "cancellation_unsupported"
    CANCELLATION_UNAVAILABLE = "cancellation_unavailable"


class OperationDetachRefusalCode(StrEnum):
    """Stable refusal codes for detach requests."""

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


class OperationResultProjectionVersionHeader(BaseModel):
    """Minimal header parsed before exact settled-result projection dispatch."""

    model_config = _PUBLIC_CONFIG
    result_projection_version: Annotated[int, Field(ge=1)]


class OperationObservationRequestV1(BaseModel):
    """Request one atomic projection and bounded event page."""

    model_config = _PUBLIC_CONFIG

    observation_version: Literal[1] = 1
    operation_id: OperationId
    after_cursor: OperationEventCursor
    page_limit: OperationReplayLimit


class OperationReviewProjectionRequestV1(BaseModel):
    """Versioned request for a safe REVIEW projection."""

    model_config = _PUBLIC_CONFIG
    review_projection_version: Literal[1] = 1
    reference: OperationReviewProjectionReferenceV1


class OperationReviewProjectionSuccessV1[ReviewProjectionT: BaseModel](BaseModel):
    """Successful typed REVIEW projection response."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    review_projection_version: Literal[1] = 1
    projection_schema: OperationSchemaIdentityV1
    definition_contract_digest: ContentDigest
    projection: ReviewProjectionT


class OperationReviewProjectionRefusalV1(BaseModel):
    """Renderer-neutral refusal for a REVIEW projection request."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    review_projection_version: Literal[1] = 1
    code: OperationReviewProjectionRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


class OperationResponseControlRequestV1(BaseModel):
    """Versioned request for the safe response-control surface."""

    model_config = _PUBLIC_CONFIG

    response_control_version: Literal[1] = 1
    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: OperationRevision
    actor_ref: OperationActorReference


class OperationResponseControlSuccessV1(BaseModel):
    """Successful response-control inspection result."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    response_control_version: Literal[1] = 1
    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: OperationRevision
    available: bool
    permitted_intents: frozenset[OperationResponseIntentValue]

    @model_validator(mode="after")
    def _validate_availability(self) -> OperationResponseControlSuccessV1:
        if self.available != bool(self.permitted_intents):
            raise ValueError("response-control availability must match its permitted intents")
        return self


class OperationResponseControlRefusalV1(BaseModel):
    """Renderer-neutral refusal for a response-control request."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    response_control_version: Literal[1] = 1
    code: OperationResponseControlRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


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


class OperationResponseMutationSuccessV1(BaseModel):
    """Safe acknowledgement that one exact response was durably consumed."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    response_control_version: Literal[1] = 1
    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: OperationRevision
    response_action: OperationResponseIntentValue


class OperationSubmissionReceiptV1(BaseModel):
    """Credential-free result of durable registered-operation submission."""

    model_config = _PUBLIC_CONFIG

    submission_version: Literal[1] = 1
    operation_id: OperationId
    secret_requirement: OperationSecretRequirement | None


class OperationCancellationRequestV1(BaseModel):
    """Versioned request to cooperatively cancel an operation."""

    model_config = _PUBLIC_CONFIG
    cancellation_version: Literal[1] = 1
    operation_id: OperationId
    expected_revision: OperationRevision


class OperationCancellationSuccessV1(BaseModel):
    """Successful cooperative-cancellation request result."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    cancellation_version: Literal[1] = 1
    operation_id: OperationId
    revision: OperationRevision
    cancellation_requested: Literal[True] = True
    cancellation_acknowledged: bool


class OperationCancellationRefusalV1(BaseModel):
    """Renderer-neutral refusal for a cancellation request."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    cancellation_version: Literal[1] = 1
    code: OperationCancellationRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


class OperationDetachRequestV1(BaseModel):
    """Versioned request to detach an operation from a frontend."""

    model_config = _PUBLIC_CONFIG
    detach_version: Literal[1] = 1
    operation_id: OperationId
    expected_revision: OperationRevision


class OperationDetachSuccessV1(BaseModel):
    """Successful frontend detach result."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    detach_version: Literal[1] = 1
    operation_id: OperationId
    revision: OperationRevision
    detached: Literal[True] = True


class OperationDetachRefusalV1(BaseModel):
    """Renderer-neutral refusal for a detach request."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    detach_version: Literal[1] = 1
    code: OperationDetachRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


class OperationWorkspaceRefreshTargetRequestV1(BaseModel):
    """Resolve a restart-safe target without accepting a caller result reference."""

    model_config = _PUBLIC_CONFIG

    refresh_target_version: Literal[1] = 1
    operation_id: OperationId
    terminal_revision: OperationRevision
    definition_contract_digest: ContentDigest
    target_schema: OperationSchemaIdentityV1


class OperationWorkspaceRefreshTargetSuccessV1[RefreshTargetT: BaseModel](BaseModel):
    """Successful typed workspace refresh target resolution."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    refresh_target_version: Literal[1] = 1
    target_schema: OperationSchemaIdentityV1
    definition_contract_digest: ContentDigest
    target: RefreshTargetT


class OperationWorkspaceRefreshTargetRefusalV1(BaseModel):
    """Renderer-neutral refusal for a workspace refresh-target request."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    refresh_target_version: Literal[1] = 1
    code: OperationWorkspaceRefreshTargetRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


class OperationResultProjectionRequestV1(BaseModel):
    """Resolve a settled operation's safe public result without a raw reference.

    Symmetric with :class:`OperationWorkspaceRefreshTargetRequestV1`: the
    caller never supplies the private ``result_ref`` itself, only the
    operation identity, the terminal revision it expects, the definition
    contract it trusts, and the registered result schema it wants back.
    """

    model_config = _PUBLIC_CONFIG

    result_projection_version: Literal[1] = 1
    operation_id: OperationId
    terminal_revision: OperationRevision
    definition_contract_digest: ContentDigest
    result_schema: OperationSchemaIdentityV1


class OperationResultProjectionSuccessV1[ResultProjectionT: BaseModel](BaseModel):
    """Successful typed settled-result projection."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["success"] = "success"
    result_projection_version: Literal[1] = 1
    result_schema: OperationSchemaIdentityV1
    definition_contract_digest: ContentDigest
    projection: ResultProjectionT


class OperationResultProjectionRefusalV1(BaseModel):
    """Renderer-neutral refusal for a settled-result projection request."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    result_projection_version: Literal[1] = 1
    code: OperationResultProjectionRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


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
    """Public projection of one operation phase event."""

    kind: Literal[OperationEventKind.PHASE] = OperationEventKind.PHASE
    phase_code: OperationEventCode


class OperationPublicProgressEventV1(_OperationPublicEventBase):
    """Public projection of one bounded operation progress event."""

    kind: Literal[OperationEventKind.PROGRESS] = OperationEventKind.PROGRESS
    completed: NonNegativeInt
    total: Annotated[int, Field(gt=0)]
    unit_code: OperationEventCode | None

    @model_validator(mode="after")
    def _validate_progress(self) -> OperationPublicProgressEventV1:
        if self.completed > self.total:
            raise ValueError("public progress event cannot exceed its total")
        return self


class OperationPublicLogEventV1(_OperationPublicEventBase):
    """Public projection of one structured operation log event."""

    kind: Literal[OperationEventKind.LOG] = OperationEventKind.LOG
    severity: OperationLogSeverity
    diagnostic_ref: OperationDiagnosticReference | None


class OperationPublicEffectEventV1(_OperationPublicEventBase):
    """Public projection of one operation effect event."""

    kind: Literal[OperationEventKind.EFFECT] = OperationEventKind.EFFECT
    effect: OperationEffect


class OperationPublicNoticeEventV1(_OperationPublicEventBase):
    """Public projection of one localized-notice identity event."""

    kind: Literal[OperationEventKind.NOTICE] = OperationEventKind.NOTICE
    notice_code: OperationEventCode


class OperationPublicReconciliationEventV1(_OperationPublicEventBase):
    """Public projection of one startup-reconciliation event."""

    kind: Literal[OperationEventKind.RECONCILIATION] = OperationEventKind.RECONCILIATION
    outcome: OperationReconciliationOutcome


class OperationPublicDiagnosticEventV1(_OperationPublicEventBase):
    """Public projection of one redacted diagnostic-reference event."""

    kind: Literal[OperationEventKind.DIAGNOSTIC] = OperationEventKind.DIAGNOSTIC
    diagnostic_ref: OperationDiagnosticReference


class OperationPublicInteractionEventV1(_OperationPublicEventBase):
    """Public projection of one interaction lifecycle event."""

    kind: Literal[OperationEventKind.INTERACTION] = OperationEventKind.INTERACTION
    interaction_id: OperationInteractionId


class OperationPublicTerminalEventV1(_OperationPublicEventBase):
    """Public projection of one terminal operation receipt event."""

    kind: Literal[OperationEventKind.TERMINAL] = OperationEventKind.TERMINAL
    condition: OperationTerminalCondition
    effect: OperationEffect
    result_ref: OperationReference | None
    refusal_ref: OperationReference | None
    failure_error_code: str | None
    diagnostic_ref: OperationDiagnosticReference | None

    @model_validator(mode="after")
    def _validate_settlement_references(self) -> OperationPublicTerminalEventV1:
        validate_terminal_reference_meaning(
            condition=self.condition,
            result_ref=self.result_ref,
            refusal_ref=self.refusal_ref,
            failure_error_code=self.failure_error_code,
        )
        return self


type OperationPublicEventV1 = Annotated[
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
    """Bounded public event replay page tied to one observation anchor."""

    model_config = _PUBLIC_CONFIG

    observation_version: Literal[1] = 1
    operation_id: OperationId
    anchor_cursor: OperationEventCursor
    requested_cursor: OperationEventCursor
    status: PublicReplayStatus
    events: tuple[OperationPublicEventV1, ...]
    next_cursor: OperationEventCursor
    restart_cursor: OperationEventCursor | None

    @model_validator(mode="after")
    def _validate_page(self) -> OperationPublicEventPageV1:
        _validate_event_page_requested_cursor(self)
        if self.status is OperationReplayStatus.PAGE:
            _validate_event_page_rows(self)
        elif self.status is OperationReplayStatus.CAUGHT_UP:
            _validate_caught_up_event_page(self)
        elif self.status in RESYNCHRONIZING_REPLAY_STATUSES:
            _validate_resynchronizing_event_page(self)
        _validate_event_page_anchor_bounds(self)
        return self


def _validate_event_page_requested_cursor(page: OperationPublicEventPageV1) -> None:
    """Require an observation page to start at or before its captured anchor."""
    if page.requested_cursor > page.anchor_cursor:
        raise ValueError("public event-page cursor cannot exceed its anchor")


def _validate_event_page_rows(page: OperationPublicEventPageV1) -> None:
    """Validate non-empty, contiguous rows and their final continuation cursor."""
    if not page.events:
        raise ValueError("public event page requires at least one event")
    sequences = tuple(event.sequence for event in page.events)
    if sequences[0] != page.requested_cursor + 1 or any(
        current != previous + 1 for previous, current in pairwise(sequences)
    ):
        raise ValueError("public event page must be contiguous after the requested cursor")
    if page.next_cursor != sequences[-1] or page.restart_cursor is not None:
        raise ValueError("public event page cursor does not match its final row")


def _validate_caught_up_event_page(page: OperationPublicEventPageV1) -> None:
    """Require caught-up pages to carry only their observation anchor cursor."""
    if (
        page.events
        or page.requested_cursor != page.anchor_cursor
        or page.next_cursor != page.anchor_cursor
        or page.restart_cursor is not None
    ):
        raise ValueError("caught-up public event page must equal its observation anchor cursor")


def _validate_resynchronizing_event_page(page: OperationPublicEventPageV1) -> None:
    """Require expired or compacted pages to carry an advancing restart cursor."""
    restart_cursor = page.restart_cursor
    if page.events or restart_cursor is None or page.next_cursor != restart_cursor:
        raise ValueError("resynchronizing public event page requires one restart cursor and no rows")
    if restart_cursor <= page.requested_cursor:
        raise ValueError("public restart cursor must advance beyond the requested cursor")


def _validate_event_page_anchor_bounds(page: OperationPublicEventPageV1) -> None:
    """Keep both the continuation cursor and every row within the observation anchor."""
    if page.next_cursor > page.anchor_cursor or any(event.sequence > page.anchor_cursor for event in page.events):
        raise ValueError("public event rows cannot exceed their observation anchor")


class OperationObservationSuccessV1(BaseModel):
    """Successful atomic public operation observation."""

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
    """Renderer-neutral refusal for an operation observation request."""

    model_config = _PUBLIC_CONFIG

    outcome: Literal["refused"] = "refused"
    observation_version: Literal[1] = 1
    code: OperationObservationRefusalCode
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1
    diagnostic_ref: OperationDiagnosticReference | None


type OperationObservationResultV1 = Annotated[
    OperationObservationSuccessV1 | OperationObservationRefusalV1,
    Field(discriminator="outcome"),
]
