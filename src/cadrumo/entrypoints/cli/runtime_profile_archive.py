"""CLI transport for exact-profile archive operations."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import BaseModel

from ...application.user_profile.archive_operation import (
    PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
    PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
    PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
    ProfileArchiveExportProjection,
    ProfileArchiveExportRequest,
    ProfileArchivePushProjection,
    ProfileArchivePushRequest,
    ProfileArchiveReconcileProjection,
    ProfileArchiveReconcileRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def _run_archive_operation[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    profile_id: UUID,
    definition_id: str,
    result_type: type[ProjectionT],
    expected_effects: frozenset[OperationEffect] | None,
) -> RegisteredOperationCompletion[ProjectionT]:
    """Run one exact-profile archive request and correlate its full projection."""
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        # A contained mirror re-admits each provider request and verifies all
        # ciphertext before publishing its manifest. Keep individual exchanges
        # bounded while allowing the admitted upload to finish before disconnect.
        settlement_timeout=600 if isinstance(request, ProfileArchivePushRequest) and not request.dry_run else None,
    )
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or (expected_effects is not None and completed.effect not in expected_effects)
    ):
        raise invalid_completion_error(completed)
    return completed


def run_profile_archive_export(
    ctx: typer.Context,
    request: ProfileArchiveExportRequest,
) -> ProfileArchiveExportProjection:
    """Return the exact-profile archive receipt after a confirmed local write."""
    completed = _run_archive_operation(
        ctx,
        request,
        profile_id=request.profile_id,
        definition_id=PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
        result_type=ProfileArchiveExportProjection,
        expected_effects=frozenset({OperationEffect.UPDATED}),
    )
    projection = completed.projection
    if (
        projection.profile_id != request.profile_id
        or str(projection.receipt.bucket_id) != str(request.profile_id)
        or projection.receipt.target != str(request.target)
    ):
        raise invalid_completion_error(completed)
    return projection


def run_profile_archive_push(
    ctx: typer.Context,
    request: ProfileArchivePushRequest,
) -> ProfileArchivePushProjection:
    """Return the complete mirror report correlated to its submitted filters."""
    expected_effects = (
        frozenset({OperationEffect.NONE})
        if request.dry_run
        else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    )
    completed = _run_archive_operation(
        ctx,
        request,
        profile_id=request.profile_id,
        definition_id=PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
        result_type=ProfileArchivePushProjection,
        expected_effects=expected_effects,
    )
    projection = completed.projection
    report = projection.report
    if (
        projection.profile_id != request.profile_id
        or report.profile != str(request.profile_id)
        or report.dry_run is not request.dry_run
        or report.namespace_filter != request.namespace_filter
        or report.limit != request.limit
    ):
        raise invalid_completion_error(completed)
    return projection


def run_profile_archive_reconcile(
    ctx: typer.Context,
    request: ProfileArchiveReconcileRequest,
) -> ProfileArchiveReconcileProjection:
    """Return reconciliation rows from the exact admitted profile's journals."""
    completed = _run_archive_operation(
        ctx,
        request,
        profile_id=request.profile_id,
        definition_id=PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
        result_type=ProfileArchiveReconcileProjection,
        expected_effects=None,
    )
    projection = completed.projection
    if projection.profile_id != request.profile_id:
        raise invalid_completion_error(completed)
    return projection


__all__ = [
    "run_profile_archive_export",
    "run_profile_archive_push",
    "run_profile_archive_reconcile",
]
