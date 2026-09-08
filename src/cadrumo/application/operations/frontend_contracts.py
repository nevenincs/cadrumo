"""Strict renderer-neutral DTOs for the public operation application boundary."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ...core.identity import ContentDigest
from ...core.operations import (
    LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST,
    OperationCancellation,
    OperationClosePolicy,
    OperationEffect,
    OperationEventKind,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ...core.time.utc import validate_utc_aware
from .event_replay import OperationEventCursor
from .events import OperationEventCode, OperationEventSequence, OperationLogSeverity
from .interactions import (
    OperationActorReference,
    OperationInteractionId,
    OperationResponseIntentValue,
)
from .models import (
    OperationDefinitionId,
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
from .registry import (
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
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


class OperationPublicProgressV1(BaseModel):
    """Renderer-neutral progress state anchored to an operation event."""

    model_config = _PUBLIC_CONFIG

    completed: NonNegativeInt
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
    """Explicit public marker for an operation with no pending interaction."""

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
    """Safe public description of an operation awaiting REVIEW."""

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
    """Public marker for a pending interaction the frontend cannot perform."""

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


type OperationPublicPendingInteractionV1 = Annotated[
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
    failure_error_code: str | None
    diagnostic_ref: OperationDiagnosticReference | None

    @model_validator(mode="after")
    def _validate_projection(self) -> OperationPublicProjectionV1:
        _validate_projection_timestamps(self)
        _validate_projection_contract(self)
        _validate_projection_timeline(self)
        _validate_projection_lifecycle(self)
        _validate_projection_pending_interaction(self)
        _validate_projection_review_interaction(self)
        _validate_projection_settlement(self)
        _validate_projection_progress(self)
        _validate_projection_cancellation_availability(self)
        _validate_projection_cancellation_facts(self)
        return self


def _validate_projection_timestamps(projection: OperationPublicProjectionV1) -> None:
    for value in (projection.started_at, projection.execution_deadline_at, projection.cleanup_deadline_at):
        if value is not None:
            validate_utc_aware(value)
    validate_utc_aware(projection.updated_at)


def _validate_projection_contract(projection: OperationPublicProjectionV1) -> None:
    contract = projection.definition_contract
    if contract.definition_id != projection.definition_id:
        raise ValueError("public projection definition does not match its contract")
    if projection.close_policy is not contract.close_policy:
        raise ValueError("public projection close policy does not match its definition contract")
    if projection.cancellation is not contract.cancellation:
        raise ValueError("public projection cancellation does not match its definition contract")


def _validate_projection_timeline(projection: OperationPublicProjectionV1) -> None:
    if projection.started_at is not None and projection.started_at > projection.updated_at:
        raise ValueError("public operation start cannot follow its last update")
    if (
        projection.started_at is not None
        and projection.execution_deadline_at is not None
        and projection.execution_deadline_at < projection.started_at
    ):
        raise ValueError("public execution deadline cannot precede operation start")
    if (
        projection.started_at is not None
        and projection.cleanup_deadline_at is not None
        and projection.cleanup_deadline_at < projection.started_at
    ):
        raise ValueError("public cleanup deadline cannot precede operation start")


def _validate_projection_lifecycle(projection: OperationPublicProjectionV1) -> None:
    terminal = projection.lifecycle is OperationLifecycle.TERMINAL
    if terminal != (projection.terminal_condition is not None):
        raise ValueError("public terminal lifecycle requires exactly one terminal condition")
    if terminal and not isinstance(projection.pending_interaction, OperationNoPendingInteractionV1):
        raise ValueError("public terminal projection cannot carry a pending interaction")
    if terminal and projection.cancellable_now:
        raise ValueError("public terminal projection cannot remain cancellable")


def _validate_projection_pending_interaction(projection: OperationPublicProjectionV1) -> None:
    pending = projection.pending_interaction
    if isinstance(pending, OperationNoPendingInteractionV1):
        return
    if projection.lifecycle is not OperationLifecycle.WAITING_FOR_INTERACTION:
        raise ValueError("public pending interaction requires waiting-for-interaction lifecycle")
    if pending.revision != projection.revision:
        raise ValueError("public pending interaction does not match the current operation revision")
    interaction_kind = (
        OperationInteractionKind.REVIEW
        if isinstance(pending, OperationReviewAvailableInteractionV1)
        else pending.interaction_kind
    )
    if interaction_kind not in projection.definition_contract.interaction_kinds:
        raise ValueError("public pending interaction kind is not declared by the definition contract")


def _validate_projection_review_interaction(projection: OperationPublicProjectionV1) -> None:
    pending = projection.pending_interaction
    if not isinstance(pending, OperationReviewAvailableInteractionV1):
        return
    contract = projection.definition_contract
    if pending.operation_id != projection.operation_id:
        raise ValueError("public REVIEW interaction does not match the current operation")
    if pending.review_reference.definition_contract_digest != contract.definition_contract_digest:
        raise ValueError("public REVIEW reference does not match the current definition contract")
    if pending.review_reference.review_projection_schema != contract.review_projection_schema:
        raise ValueError("public REVIEW reference does not match the registered projection schema")
    if pending.response_schema != contract.interaction_response_schema:
        raise ValueError("public REVIEW interaction does not match the registered response schema")


def _validate_projection_settlement(projection: OperationPublicProjectionV1) -> None:
    _validate_projection_settlement_references(projection)
    _validate_projection_failure(projection)
    _validate_projection_nonterminal_settlement(projection)


def _validate_projection_settlement_references(projection: OperationPublicProjectionV1) -> None:
    references = (projection.result_ref, projection.refusal_ref)
    if all(value is not None for value in references):
        raise ValueError("public projection cannot expose result and refusal references together")
    if projection.terminal_condition is OperationTerminalCondition.SUCCEEDED and projection.result_ref is None:
        raise ValueError("successful public projection requires a result reference")
    if projection.terminal_condition is OperationTerminalCondition.REFUSED and projection.refusal_ref is None:
        raise ValueError("refused public projection requires a refusal reference")


def _validate_projection_failure(projection: OperationPublicProjectionV1) -> None:
    if (
        projection.terminal_condition is not OperationTerminalCondition.FAILED
        and projection.failure_error_code is not None
    ):
        raise ValueError("public failure error code requires a failed terminal condition")
    if projection.failure_error_code is not None:
        from ...core.errors.error_codes import get_registered_error_code_by_code

        get_registered_error_code_by_code(projection.failure_error_code)


def _validate_projection_nonterminal_settlement(projection: OperationPublicProjectionV1) -> None:
    references = (projection.result_ref, projection.refusal_ref)
    if projection.lifecycle is not OperationLifecycle.TERMINAL and (
        any(value is not None for value in references) or projection.failure_error_code is not None
    ):
        raise ValueError("nonterminal public projection cannot expose settlement references")


def _validate_projection_progress(projection: OperationPublicProjectionV1) -> None:
    if projection.progress is None:
        return
    if (
        projection.progress.event_sequence > projection.anchor_cursor
        or projection.progress.revision > projection.revision
    ):
        raise ValueError("public progress cannot exceed its projection anchor")
    if projection.progress.phase_code != projection.phase_code:
        raise ValueError("public progress phase must match the current projection phase")


def _validate_projection_cancellation_availability(projection: OperationPublicProjectionV1) -> None:
    if projection.cancellation is OperationCancellation.UNSUPPORTED and projection.cancellable_now:
        raise ValueError("unsupported cancellation cannot be currently available")
    if projection.cancellable_now and (projection.cancellation_requested or projection.cancellation_acknowledged):
        raise ValueError("public cancellation cannot remain currently available after it is requested")
    if projection.cancellable_now and projection.lifecycle is OperationLifecycle.SETTLING:
        raise ValueError("public cancellation cannot be currently available while settlement is underway")


def _validate_projection_cancellation_facts(projection: OperationPublicProjectionV1) -> None:
    _validate_unsupported_cancellation_facts(projection)
    _validate_cancellation_request_fact(projection)
    _validate_cancellation_lifecycle(projection)
    _validate_cancellation_acknowledgement(projection)
    _validate_cancelled_terminal_fact(projection)


def _validate_unsupported_cancellation_facts(projection: OperationPublicProjectionV1) -> None:
    if projection.cancellation is OperationCancellation.UNSUPPORTED and (
        projection.cancellation_requested or projection.cancellation_acknowledged
    ):
        raise ValueError("unsupported cancellation cannot carry request or acknowledgement facts")


def _validate_cancellation_request_fact(projection: OperationPublicProjectionV1) -> None:
    if projection.cancellation_requested != (projection.cleanup_deadline_at is not None):
        raise ValueError("public cleanup deadline and cancellation request must be declared together")


def _validate_cancellation_lifecycle(projection: OperationPublicProjectionV1) -> None:
    if projection.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED and not projection.cancellation_requested:
        raise ValueError("cancellation-requested lifecycle requires its declared request fact")
    if projection.cancellation_requested and projection.lifecycle in LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST:
        raise ValueError("public cancellation request disagrees with the current lifecycle")


def _validate_cancellation_acknowledgement(projection: OperationPublicProjectionV1) -> None:
    if projection.cancellation_acknowledged and not projection.cancellation_requested:
        raise ValueError("cancellation acknowledgement requires a cancellation request")
    if projection.cancellation_acknowledged and projection.lifecycle not in {
        OperationLifecycle.SETTLING,
        OperationLifecycle.TERMINAL,
    }:
        raise ValueError("cancellation acknowledgement requires settling or terminal lifecycle")


def _validate_cancelled_terminal_fact(projection: OperationPublicProjectionV1) -> None:
    if (
        projection.terminal_condition is OperationTerminalCondition.CANCELLED
        and not projection.cancellation_acknowledged
    ):
        raise ValueError("cancelled public operation requires cancellation acknowledgement")


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


type OperationReviewProjectionResultV1[ReviewProjectionT: BaseModel] = Annotated[
    OperationReviewProjectionSuccessV1[ReviewProjectionT] | OperationReviewProjectionRefusalV1,
    Field(discriminator="outcome"),
]


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


type OperationResponseControlResultV1 = Annotated[
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


type OperationResponseMutationRequestV1 = Annotated[
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
    response_action: OperationResponseIntentValue


type OperationResponseMutationResultV1 = Annotated[
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


type OperationCancellationResultV1 = Annotated[
    OperationCancellationSuccessV1 | OperationCancellationRefusalV1,
    Field(discriminator="outcome"),
]


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


type OperationDetachResultV1 = Annotated[
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


type OperationWorkspaceRefreshTargetResultV1[RefreshTargetT: BaseModel] = Annotated[
    OperationWorkspaceRefreshTargetSuccessV1[RefreshTargetT] | OperationWorkspaceRefreshTargetRefusalV1,
    Field(discriminator="outcome"),
]


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


type OperationResultProjectionResultV1[ResultProjectionT: BaseModel] = Annotated[
    OperationResultProjectionSuccessV1[ResultProjectionT] | OperationResultProjectionRefusalV1,
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
    "OperationResponseApplyRequestV1",
    "OperationResponseControlRefusalCode",
    "OperationResponseControlRefusalV1",
    "OperationResponseControlRequestV1",
    "OperationResponseControlResultV1",
    "OperationResponseControlSuccessV1",
    "OperationResponseControlVersionHeader",
    "OperationResponseMutationRequestV1",
    "OperationResponseMutationResultV1",
    "OperationResponseMutationSuccessV1",
    "OperationResponseRejectRequestV1",
    "OperationResultProjectionRefusalCode",
    "OperationResultProjectionRefusalV1",
    "OperationResultProjectionRequestV1",
    "OperationResultProjectionResultV1",
    "OperationResultProjectionSuccessV1",
    "OperationResultProjectionVersionHeader",
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
