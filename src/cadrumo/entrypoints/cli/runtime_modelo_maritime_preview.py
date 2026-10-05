"""Run the maritime preview through the authenticated profile worker."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import typer

from ...application.modelo.maritime_preview_operation import (
    MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
    ModeloMaritimePreviewProjection,
    ModeloMaritimePreviewRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def preview_modelo_maritime_exemption(
    ctx: typer.Context,
    *,
    annual_salary: Decimal | None,
    qualifying_days: int | None,
    gross_navigation_income: Decimal | None,
) -> ModeloMaritimePreviewProjection:
    """Submit parsed operator inputs to the bound profile's registered worker."""
    client = bound_profile_client(ctx)
    request = ModeloMaritimePreviewRequest(
        profile_id=client.profile_id,
        annual_salary=str(annual_salary) if annual_salary is not None else None,
        qualifying_days=qualifying_days,
        gross_navigation_income=str(gross_navigation_income) if gross_navigation_income is not None else None,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloMaritimePreviewProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    values = {row.casilla_id: row.value for row in projection.casilla_values}
    if (
        _maritime_preview_receipt_invalid(completed, projection, client.profile_id)
        or len(values) != len(projection.casilla_values)
        or values != {row.casilla_id: row.value for row in projection.observations}
    ):
        raise invalid_completion_error(completed)
    return projection


__all__ = ["preview_modelo_maritime_exemption"]


def _maritime_preview_receipt_invalid(
    completed: RegisteredOperationCompletion[ModeloMaritimePreviewProjection],
    projection: ModeloMaritimePreviewProjection,
    profile_id: UUID,
) -> bool:
    """Require a settled read-only preview for the admitted profile."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or (projection.profile_id != profile_id)
    )
