"""Run the maritime preview through the authenticated profile worker."""

from __future__ import annotations

from decimal import Decimal
from typing import Never

import typer
from pydantic import BaseModel

from ...application.modelo.maritime_preview_operation import (
    MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
    ModeloMaritimePreviewProjection,
    ModeloMaritimePreviewRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
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
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or len(values) != len(projection.casilla_values)
        or values != {row.casilla_id: row.value for row in projection.observations}
    ):
        _invalid(completed)
    return projection


__all__ = ["preview_modelo_maritime_exemption"]
