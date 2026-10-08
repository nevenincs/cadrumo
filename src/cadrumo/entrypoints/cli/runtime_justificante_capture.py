"""CLI bridge for exact-profile live justificante capture."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.live.justificante_capture_operation import (
    JUSTIFICANTE_CAPTURE_DEFINITION_ID,
    JustificanteCapturePublicResultV1,
    JustificanteCaptureRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_deadlines import provider_login_settlement_seconds
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


@dataclass(frozen=True, slots=True)
class JustificanteCaptureRead:
    """Keep the settled runtime receipt with the restored capture projection."""

    completion: RegisteredOperationCompletion[JustificanteCapturePublicResultV1]
    projection: JustificanteCapturePublicResultV1


def capture_justificante_for_cli(
    ctx: typer.Context,
    *,
    profile_id: UUID,
    modelo: str,
    year: int,
    period: Period,
) -> JustificanteCaptureRead:
    """Submit one receipt capture through the profile-bound operation worker."""
    if period.filing_year != year:
        raise typer.BadParameter("justificante capture period year does not match the requested year")

    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = JustificanteCaptureRequest(
        profile_id=profile_id,
        modelo=modelo,
        year=year,
        period=period.registry_token,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=JUSTIFICANTE_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=JustificanteCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
        settlement_timeout=provider_login_settlement_seconds(after_login=120),
    )
    try:
        projection = completed.projection
        if not isinstance(projection, JustificanteCapturePublicResultV1):
            raise ValueError("justificante capture projection has an invalid type")
        if _justificante_capture_scope_invalid(projection, profile_id, modelo, year, request):
            raise ValueError("justificante capture result does not match its submitted scope")
        if _justificante_capture_receipt_invalid(completed):
            raise ValueError("justificante capture result disagrees with its settled receipt")
        if (
            projection.calendar_evidence_available != projection.justificante_metadata_registered
            or projection.modelo_filing_record_required != (not projection.filing_evidence_stamped)
            or projection.filing_evidence_stamped != (projection.filing_record_id is not None)
        ):
            raise ValueError("justificante capture result contains inconsistent evidence flags")
    except Exception:
        raise invalid_completion_error(completed) from None
    return JustificanteCaptureRead(completion=completed, projection=projection)


__all__ = ["JustificanteCaptureRead", "capture_justificante_for_cli"]


def _justificante_capture_scope_invalid(
    projection: JustificanteCapturePublicResultV1,
    profile_id: UUID,
    modelo: str,
    year: int,
    request: JustificanteCaptureRequest,
) -> bool:
    """Correlate captured filing evidence with the exact requested profile and declaration coordinates."""
    return (
        str(projection.bucket_id) != str(profile_id)
        or str(projection.modelo) != modelo
        or projection.filing_year != year
        or (str(projection.period) != request.period)
    )


def _justificante_capture_receipt_invalid(
    completed: RegisteredOperationCompletion[JustificanteCapturePublicResultV1],
) -> bool:
    """Require the successful mutation receipt without a refusal code."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
    )
