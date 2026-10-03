"""Exact-profile read executors for the application review queue."""

from __future__ import annotations

from decimal import Decimal
from functools import partial

from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import override_settings
from ...core.operations import profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.read_capture import capture_read_result
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .operator import project_review_item, project_review_queue
from .read_contracts import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadRequest,
    ReviewReadOperationPorts,
    ReviewViewReadRequest,
)
from .read_projections import (
    ReviewQueueReadExecutionResult,
    ReviewViewReadExecutionResult,
    snapshot_review_row,
)


class ReviewQueueReadExecutor:
    """Capture canonical queue rows through exact-profile read ports."""

    def __init__(self, ports: ReviewReadOperationPorts) -> None:
        """Bind the exact-profile source readers."""
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
            rows=tuple(snapshot_review_row(row) for row in report.rows),
        )

    async def execute(
        self,
        request: OperationRequest[ReviewQueueReadRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture one no-effect queue result under the worker authority pin."""
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

        return await capture_read_result(
            context, partial(self._capture, payload, context.authority_operation), task_name="review-queue-read"
        )


class ReviewViewReadExecutor:
    """Capture one canonical review item through exact-profile read ports."""

    def __init__(self, ports: ReviewReadOperationPorts) -> None:
        """Bind the exact-profile source readers."""
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
            row=snapshot_review_row(row),
        )

    async def execute(
        self,
        request: OperationRequest[ReviewViewReadRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture one no-effect item result under the worker authority pin."""
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

        return await capture_read_result(
            context, partial(self._capture, payload, context.authority_operation), task_name="review-item-read"
        )


__all__ = ["ReviewQueueReadExecutor", "ReviewViewReadExecutor"]
