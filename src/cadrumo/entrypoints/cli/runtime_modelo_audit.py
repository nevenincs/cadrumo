"""Registered-operation bridge for exact-profile Modelo evidence audits."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Never
from uuid import UUID

import typer
from pydantic import BaseModel

from ...application.evidence.models import EvidenceBundle
from ...application.evidence.service import EvidenceBundleVerificationReport
from ...application.modelo.audit_operation import (
    MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_AUDIT_READ_OPERATION_DEFINITION_ID,
    ModeloAuditExportProjection,
    ModeloAuditExportRequest,
    ModeloAuditReadProjection,
    ModeloAuditReadRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client, require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def _submit[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    profile_id: UUID,
    definition_id: str,
    result_type: type[ProjectionT],
) -> RegisteredOperationCompletion[ProjectionT]:
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    return completed


def _read_modelo_audit(
    ctx: typer.Context,
    *,
    kind: Literal["view", "check"],
    bundle_id: str,
) -> tuple[RegisteredOperationCompletion[ModeloAuditReadProjection], ModeloAuditReadProjection]:
    """Submit one public audit read and correlate its complete projection."""
    client = bound_profile_client(ctx)
    request = ModeloAuditReadRequest(profile_id=client.profile_id, kind=kind, bundle_id=bundle_id)
    completed = _submit(
        ctx,
        request,
        profile_id=client.profile_id,
        definition_id=MODELO_AUDIT_READ_OPERATION_DEFINITION_ID,
        result_type=ModeloAuditReadProjection,
    )
    projection = completed.projection
    bundle = projection.bundle
    report = projection.report
    selector = request.bundle_id.strip()
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or projection.kind != request.kind
        or (request.kind == "view" and (bundle is None or report is not None))
        or (request.kind == "check" and (report is None or bundle is not None))
        or (
            bundle is not None
            and (bundle.bucket_id != str(client.profile_id) or not bundle.bundle_id.startswith(selector))
        )
        or (report is not None and not report.bundle_id.startswith(selector))
    ):
        _invalid(completed)
    return completed, projection


def read_modelo_audit_view(ctx: typer.Context, *, bundle_id: str) -> EvidenceBundle:
    """Return a full canonical manifest from the exact-profile worker."""
    completed, projection = _read_modelo_audit(ctx, kind="view", bundle_id=bundle_id)
    if projection.bundle is None:
        _invalid(completed)
    return projection.bundle.to_bundle()


def check_modelo_audit(ctx: typer.Context, *, bundle_id: str) -> EvidenceBundleVerificationReport:
    """Return the complete canonical verification report from the worker."""
    completed, projection = _read_modelo_audit(ctx, kind="check", bundle_id=bundle_id)
    if projection.report is None:
        _invalid(completed)
    return projection.report.to_report()


def export_modelo_audit(
    ctx: typer.Context,
    *,
    bundle_id: str,
    output: Path,
    force_incomplete: bool = False,
) -> ModeloAuditExportProjection:
    """Return a confirmed output receipt from the exact-profile export worker."""
    client = bound_profile_client(ctx)
    request = ModeloAuditExportRequest(
        profile_id=client.profile_id,
        bundle_id=bundle_id,
        output=output,
        force_incomplete=force_incomplete,
    )
    completed = _submit(
        ctx,
        request,
        profile_id=client.profile_id,
        definition_id=MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
        result_type=ModeloAuditExportProjection,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or not projection.bundle_id.startswith(request.bundle_id.strip())
        or projection.output != str(request.output)
    ):
        _invalid(completed)
    return projection


__all__ = ["check_modelo_audit", "export_modelo_audit", "read_modelo_audit_view"]
