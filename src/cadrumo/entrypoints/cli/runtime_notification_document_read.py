"""CLI bridges for exact-profile notification-document custody reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.live.notification_document_read_operation import (
    NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
    NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
    NotificationDocumentHistoryPublicResultV1,
    NotificationDocumentHistoryRequest,
    NotificationDocumentViewPublicResultV1,
    NotificationDocumentViewRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .errors import CliRefusedBoundaryError
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class NotificationDocumentViewRead:
    """Keep the settled receipt beside one exact-document public projection."""

    completion: RegisteredOperationCompletion[NotificationDocumentViewPublicResultV1]
    projection: NotificationDocumentViewPublicResultV1


@dataclass(frozen=True, slots=True)
class NotificationDocumentHistoryRead:
    """Keep the settled receipt beside parsed document-history projections."""

    completion: RegisteredOperationCompletion[NotificationDocumentHistoryPublicResultV1]
    projection: NotificationDocumentHistoryPublicResultV1


_NotificationDocumentReadCompletion = (
    RegisteredOperationCompletion[NotificationDocumentViewPublicResultV1]
    | RegisteredOperationCompletion[NotificationDocumentHistoryPublicResultV1]
)


def _require_read_receipt(completed: _NotificationDocumentReadCompletion) -> None:
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise ValueError("notification-document read result disagrees with its settled receipt")


def _invalid_frame(completed: _NotificationDocumentReadCompletion) -> CliRefusedBoundaryError:
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def read_notification_document_view_for_cli(
    ctx: typer.Context,
    *,
    profile_id: UUID,
    certificado_id: str,
) -> NotificationDocumentViewRead:
    """Read one exact certificado through its profile-bound registered operation."""
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationDocumentViewRequest(profile_id=profile_id, certificado_id=certificado_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=NotificationDocumentViewPublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, NotificationDocumentViewPublicResultV1):
            raise ValueError("notification-document view projection has an invalid type")
        if projection.bucket_id != str(profile_id) or projection.certificado_id != request.certificado_id:
            raise ValueError("notification-document view result does not match its submitted scope")
        _require_read_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return NotificationDocumentViewRead(completion=completed, projection=projection)


def read_notification_document_history_for_cli(
    ctx: typer.Context,
    *,
    profile_id: UUID,
) -> NotificationDocumentHistoryRead:
    """Read parsed notification-document history for one exact profile."""
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationDocumentHistoryRequest(profile_id=profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=NotificationDocumentHistoryPublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, NotificationDocumentHistoryPublicResultV1):
            raise ValueError("notification-document history projection has an invalid type")
        if projection.bucket_id != str(profile_id) or projection.count != len(projection.documents):
            raise ValueError("notification-document history result does not match its submitted profile and rows")
        _require_read_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return NotificationDocumentHistoryRead(completion=completed, projection=projection)


__all__ = [
    "NotificationDocumentHistoryRead",
    "NotificationDocumentViewRead",
    "read_notification_document_history_for_cli",
    "read_notification_document_view_for_cli",
]
