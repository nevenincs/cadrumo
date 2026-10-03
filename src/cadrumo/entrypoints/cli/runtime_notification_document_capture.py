"""CLI bridge for exact-profile notification-document custody capture."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.live.notification_document_capture_operation import (
    NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
    NotificationDocumentCapturePublicResultV1,
    NotificationDocumentCaptureRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


@dataclass(frozen=True, slots=True)
class NotificationDocumentCapture:
    """Keep the settled receipt with its safe document-custody summary."""

    completion: RegisteredOperationCompletion[NotificationDocumentCapturePublicResultV1]
    projection: NotificationDocumentCapturePublicResultV1


def capture_notification_document_for_cli(
    ctx: typer.Context,
    *,
    profile_id: UUID,
    certificado_id: str,
) -> NotificationDocumentCapture:
    """Submit one document capture through the profile-bound operation worker."""
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationDocumentCaptureRequest(profile_id=profile_id, certificado_id=certificado_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=NotificationDocumentCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, NotificationDocumentCapturePublicResultV1):
            raise ValueError("notification-document capture projection has an invalid type")
        if projection.bucket_id != str(profile_id) or projection.certificado_id != request.certificado_id:
            raise ValueError("notification-document capture result does not match its submitted scope")
        if _notification_document_receipt_invalid(completed, projection):
            raise ValueError("notification-document capture result disagrees with its settled receipt")
    except Exception:
        raise invalid_completion_error(completed) from None
    return NotificationDocumentCapture(completion=completed, projection=projection)


__all__ = ["NotificationDocumentCapture", "capture_notification_document_for_cli"]


def _notification_document_receipt_invalid(
    completed: RegisteredOperationCompletion[NotificationDocumentCapturePublicResultV1],
    projection: NotificationDocumentCapturePublicResultV1,
) -> bool:
    """Require an exact updated-or-idempotent receipt consistent with document custody."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or (completed.effect is OperationEffect.NONE and (not projection.already_in_custody))
        or (completed.effect is OperationEffect.UPDATED and projection.already_in_custody)
        or (completed.effect not in (OperationEffect.UPDATED, OperationEffect.NONE))
    )
