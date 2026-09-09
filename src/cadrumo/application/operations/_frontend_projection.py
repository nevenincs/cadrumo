"""Renderer-neutral operation projection contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ...core.identity import ContentDigest
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ...core.time.utc import validate_utc_aware
from .event_replay import OperationEventCursor
from .events import OperationEventCode, OperationEventSequence
from .interactions import OperationInteractionId
from .models import (
    OperationDefinitionId,
    OperationDiagnosticReference,
    OperationId,
    OperationReference,
    OperationRevision,
)
from .registry import OperationPublicDefinitionContractV1, OperationSchemaIdentityV1

_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

type OperationPublicPendingInteractionV1 = Annotated[
    OperationNoPendingInteractionV1 | OperationReviewAvailableInteractionV1 | OperationUnsupportedInteractionV1,
    Field(discriminator="disposition"),
]


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
        # Keep the projection module importable on its own.  The public
        # facade loads this module before the request contracts, while the
        # facade's historical validation helpers refer back to this model.
        # Resolving those helpers only when a projection is validated avoids
        # importing the facade while this module is still defining its model.
        from .frontend_contracts import (
            validate_projection_cancellation_facts,
            validate_projection_contract,
            validate_projection_settlement,
        )

        for value in (self.started_at, self.execution_deadline_at, self.cleanup_deadline_at):
            if value is not None:
                validate_utc_aware(value)
        validate_utc_aware(self.updated_at)
        validate_projection_contract(self)
        _validate_projection_timeline(self)
        _validate_projection_lifecycle(self)
        _validate_projection_pending_interaction(self)
        _validate_projection_review_interaction(self)
        validate_projection_settlement(self)
        _validate_projection_progress(self)
        _validate_projection_cancellation_availability(self)
        validate_projection_cancellation_facts(self)
        return self


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
