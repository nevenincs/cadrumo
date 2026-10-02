"""Exact-profile, read-only operations for the application review queue."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings, override_settings
from ...core.external_constants import OutputLanguage
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ...core.unit_proportion import is_unit_proportion
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import LegalRefId
from ..filing.draft_review_ports import DraftReviewPorts
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicDecimal
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .enums import ReviewSeverity, ReviewState, severity_rank
from .operator import ReviewQueueRow, project_review_item, project_review_queue

REVIEW_QUEUE_OPERATION_DEFINITION_ID = "app.review.queue"
REVIEW_VIEW_OPERATION_DEFINITION_ID = "app.review.view"
_MAX_SELECTOR_COUNT = 128
_ReviewSelectors = Annotated[tuple[str, ...], Field(max_length=_MAX_SELECTOR_COUNT)]
_QueueRows = Annotated[tuple["ReviewQueueRowProjection", ...], Field(max_length=4_096)]


class ReviewReadPortsFactory(Protocol):
    """Create the canonical review reader capabilities under the worker pin."""

    def __call__(
        self,
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
    ) -> DraftReviewPorts:
        """Return the encrypted source readers for this exact profile and pin."""
        ...


@dataclass(frozen=True, slots=True)
class ReviewReadOperationPorts:
    """Dependencies shared by the two immutable review reads."""

    settings: Settings
    draft_review_ports_factory: ReviewReadPortsFactory


class ReviewQueueReadRequest(CredentialFreeOperationRequest):
    """One ordered, profile-wide queue query."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    kinds: _ReviewSelectors = ()
    source_kinds: _ReviewSelectors = ()
    state: ReviewState = ReviewState.PENDING
    modelo: str | None = None
    confidence_below: PublicDecimal | None = None
    output_language: OutputLanguage

    @model_validator(mode="after")
    def _confidence_threshold(self) -> Self:
        if self.confidence_below is not None and not is_unit_proportion(Decimal(self.confidence_below.decimal)):
            raise ValueError("review confidence threshold must be between zero and one")
        return self


class ReviewViewReadRequest(CredentialFreeOperationRequest):
    """One exact review item lookup in the active profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    item_id: str = Field(min_length=1)
    output_language: OutputLanguage


class ReviewQueueRowProjection(BaseModel):
    """Closed wire snapshot of every operator-facing review-row fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    item_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    source_kind: str | None = None
    affected_object_id: str = Field(min_length=1)
    bucket_id: BucketId
    modelo: str | None = None
    period: str | None = None
    severity: ReviewSeverity
    state: ReviewState
    blocking: bool
    reason: str = ""
    current_owner_surface: str = Field(min_length=1)
    canonical_next_command: str = Field(min_length=1)
    since: datetime
    summary: str = Field(min_length=1)
    legal_refs: tuple[LegalRefId, ...] = ()

    @field_validator("since")
    @classmethod
    def _utc_instant(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)


class ReviewQueueReadExecutionResult(BaseModel):
    """Worker-captured queue rows with their exact request provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    request: ReviewQueueReadRequest
    rows: _QueueRows

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_queue_scope(self.profile_id, self.request, self.rows)
        return self


class ReviewQueueReadProjection(BaseModel):
    """Independent public projection of the successful worker capture."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    request: ReviewQueueReadRequest
    rows: _QueueRows

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_queue_scope(self.profile_id, self.request, self.rows)
        return self


class ReviewViewReadExecutionResult(BaseModel):
    """Worker-captured item with its exact lookup provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    request: ReviewViewReadRequest
    row: ReviewQueueRowProjection

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_view_scope(self.profile_id, self.request, self.row)
        return self


class ReviewViewReadProjection(BaseModel):
    """Independent public projection of the successful exact-item read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    request: ReviewViewReadRequest
    row: ReviewQueueRowProjection

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_view_scope(self.profile_id, self.request, self.row)
        return self


def _validate_queue_scope(
    profile_id: UUID,
    request: ReviewQueueReadRequest,
    rows: tuple[ReviewQueueRowProjection, ...],
) -> None:
    if request.profile_id != profile_id:
        raise ValueError("review queue result profile differs from its request")
    bucket_id = str(profile_id)
    if any(row.bucket_id != bucket_id or row.state is not request.state for row in rows):
        raise ValueError("review queue row scope differs from its request")
    if len({row.item_id for row in rows}) != len(rows):
        raise ValueError("review queue contains duplicate item identities")
    accepted_kinds = frozenset(value.strip() for value in request.kinds if value.strip())
    accepted_source_kinds = frozenset(value.strip() for value in request.source_kinds if value.strip())
    if any(
        (accepted_kinds and row.kind not in accepted_kinds)
        or (accepted_source_kinds and (row.source_kind is None or row.source_kind not in accepted_source_kinds))
        or (request.modelo is not None and row.modelo != request.modelo)
        for row in rows
    ):
        raise ValueError("review queue rows do not satisfy their request filters")
    ordered = tuple(sorted(rows, key=lambda row: (-severity_rank(row.severity), row.since, row.item_id)))
    if ordered != rows:
        raise ValueError("review queue rows are not in canonical order")


def _validate_view_scope(
    profile_id: UUID,
    request: ReviewViewReadRequest,
    row: ReviewQueueRowProjection,
) -> None:
    if request.profile_id != profile_id or row.bucket_id != str(profile_id) or row.item_id != request.item_id:
        raise ValueError("review item result differs from its request")
    if row.state is not ReviewState.ALL:
        raise ValueError("review item result is not an all-state lookup")


def _snapshot(row: ReviewQueueRow) -> ReviewQueueRowProjection:
    return ReviewQueueRowProjection.model_validate(row.model_dump(mode="python"), strict=True)


def _check_receipt(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    expected_type: type[BaseModel],
    definition_id: str,
) -> UUID:
    if type(result) is not expected_type:
        raise ValueError("invalid review read result")
    profile_id = getattr(result, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise ValueError("invalid review read profile")
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("review read result contradicts its terminal receipt")
    return profile_id


def _project_queue_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ReviewQueueReadProjection:
    profile_id = _check_receipt(
        result,
        receipt,
        expected_type=ReviewQueueReadExecutionResult,
        definition_id=REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    )
    private = ReviewQueueReadExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    if private.profile_id != profile_id:
        raise ValueError("review queue profile changed during projection")
    return ReviewQueueReadProjection(profile_id=profile_id, request=private.request, rows=private.rows)


def _project_view_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ReviewViewReadProjection:
    profile_id = _check_receipt(
        result,
        receipt,
        expected_type=ReviewViewReadExecutionResult,
        definition_id=REVIEW_VIEW_OPERATION_DEFINITION_ID,
    )
    private = ReviewViewReadExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    if private.profile_id != profile_id:
        raise ValueError("review item profile changed during projection")
    return ReviewViewReadProjection(profile_id=profile_id, request=private.request, row=private.row)


class ReviewQueueReadExecutor:
    """Capture canonical queue rows through exact-profile read ports."""

    def __init__(self, ports: ReviewReadOperationPorts) -> None:
        self._ports = ports

    def _capture(
        self,
        payload: ReviewQueueReadRequest,
        operation: PinnedAuthorityOperation,
    ) -> ReviewQueueReadExecutionResult:
        bucket_id = str(payload.profile_id)
        reader_ports = self._ports.draft_review_ports_factory(bucket_id=bucket_id, operation=operation)
        with override_settings(cadrumo_output_language=payload.output_language.value):
            report = project_review_queue(
                bucket_id=bucket_id,
                operation=operation,
                settings=self._ports.settings,
                kinds=payload.kinds,
                source_kinds=payload.source_kinds,
                state=payload.state,
                modelo=payload.modelo,
                confidence_below=(
                    Decimal(payload.confidence_below.decimal) if payload.confidence_below is not None else None
                ),
                ports=reader_ports,
            )
        return ReviewQueueReadExecutionResult(
            profile_id=payload.profile_id,
            request=payload,
            rows=tuple(_snapshot(row) for row in report.rows),
        )

    async def execute(
        self,
        request: OperationRequest[ReviewQueueReadRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        if (
            request.definition_id != REVIEW_QUEUE_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(REVIEW_QUEUE_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(self._capture, payload, context.authority_operation)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="review-queue-read")


class ReviewViewReadExecutor:
    """Capture one canonical review item through exact-profile read ports."""

    def __init__(self, ports: ReviewReadOperationPorts) -> None:
        self._ports = ports

    def _capture(
        self,
        payload: ReviewViewReadRequest,
        operation: PinnedAuthorityOperation,
    ) -> ReviewViewReadExecutionResult:
        bucket_id = str(payload.profile_id)
        reader_ports = self._ports.draft_review_ports_factory(bucket_id=bucket_id, operation=operation)
        with override_settings(cadrumo_output_language=payload.output_language.value):
            row = project_review_item(
                payload.item_id,
                bucket_id=bucket_id,
                operation=operation,
                settings=self._ports.settings,
                ports=reader_ports,
            )
        return ReviewViewReadExecutionResult(
            profile_id=payload.profile_id,
            request=payload,
            row=_snapshot(row),
        )

    async def execute(
        self,
        request: OperationRequest[ReviewViewReadRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        if (
            request.definition_id != REVIEW_VIEW_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(REVIEW_VIEW_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(self._capture, payload, context.authority_operation)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="review-item-read")


def _build_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    build: Callable[[], object],
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=build,
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {
                OperationFrontendProjection.CLI,
                OperationFrontendProjection.TUI,
                OperationFrontendProjection.MCP,
            }
        ),
    )


def build_review_read_definitions(ports: ReviewReadOperationPorts) -> tuple[OperationDefinition, ...]:
    """Build the exact queue and item-view definitions over shared read ports."""
    return (
        _build_definition(
            definition_id=REVIEW_QUEUE_OPERATION_DEFINITION_ID,
            request_type=ReviewQueueReadRequest,
            result_type=ReviewQueueReadExecutionResult,
            executor_type=ReviewQueueReadExecutor,
            build=lambda: ReviewQueueReadExecutor(ports),
        ),
        _build_definition(
            definition_id=REVIEW_VIEW_OPERATION_DEFINITION_ID,
            request_type=ReviewViewReadRequest,
            result_type=ReviewViewReadExecutionResult,
            executor_type=ReviewViewReadExecutor,
            build=lambda: ReviewViewReadExecutor(ports),
        ),
    )


def _resolve_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    definition_id: str,
    request_type: type[BaseModel],
) -> ResolvedOperationAccess:
    if request.definition_id != definition_id or type(request.payload) is not request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = getattr(request.payload, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=profile_id, periods=frozenset())


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    projector: Callable[[BaseModel, OperationTerminalReceipt], BaseModel],
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=result_type,
        ),
        result_projector=projector,
        access_resolver=lambda request, context: _resolve_access(
            request,
            context,
            definition_id=definition.definition_id,
            request_type=request_type,
        ),
    )


def build_review_read_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind both exact-profile requests to independent closed projections."""
    by_id = {definition.definition_id: definition for definition in definitions}
    expected = {REVIEW_QUEUE_OPERATION_DEFINITION_ID, REVIEW_VIEW_OPERATION_DEFINITION_ID}
    if len(by_id) != len(definitions) or set(by_id) != expected:
        raise ValueError("review registration requires the exact queue and view definitions")
    return (
        _registration(
            by_id[REVIEW_QUEUE_OPERATION_DEFINITION_ID],
            request_type=ReviewQueueReadRequest,
            result_type=ReviewQueueReadProjection,
            projector=_project_queue_result,
        ),
        _registration(
            by_id[REVIEW_VIEW_OPERATION_DEFINITION_ID],
            request_type=ReviewViewReadRequest,
            result_type=ReviewViewReadProjection,
            projector=_project_view_result,
        ),
    )


__all__ = [
    "REVIEW_QUEUE_OPERATION_DEFINITION_ID",
    "REVIEW_VIEW_OPERATION_DEFINITION_ID",
    "ReviewQueueReadProjection",
    "ReviewQueueReadRequest",
    "ReviewQueueRowProjection",
    "ReviewReadOperationPorts",
    "ReviewReadPortsFactory",
    "ReviewViewReadProjection",
    "ReviewViewReadRequest",
    "build_review_read_definitions",
    "build_review_read_registrations",
]
