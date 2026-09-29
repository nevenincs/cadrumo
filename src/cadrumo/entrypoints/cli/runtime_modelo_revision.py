"""CLI read of full revision values through the exact-profile runtime."""

from __future__ import annotations

from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ...application.modelo.revision_inventory_operation import (
    MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionsProjection,
    ModeloWorkRevisionsRequest,
)
from ...application.modelo.revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionSnapshotProjection,
    ModeloWorkRevisionSnapshotRequest,
)
from ...application.modelo.selectors import ModeloCalculationRevisionSelector
from ...application.runtime.contracts import RuntimeRefusalCode
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_modelo_metadata import read_modelo_work_unit
from .runtime_modelo_verification import select_modelo_work_revision_for_cli
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_modelo_revision_inventory_for_cli(
    ctx: typer.Context,
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
) -> ModeloWorkRevisionsProjection:
    """Resolve an optional unit through metadata, then read its authorized inventory."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    if bucket_id is not None and bucket_id.strip() and bucket_id.strip() != str(client.profile_id):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    selected_id = None
    if any(value is not None for value in (work_unit_id, modelo, year, period)):
        unit = read_modelo_work_unit(
            ctx,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        )
        selected_id = unit.work_unit_id
    completed = run_registered_operation(
        client,
        ModeloWorkRevisionsRequest(profile_id=client.profile_id, work_unit_id=selected_id),
        definition_id=MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloWorkRevisionsProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if (
        not isinstance(result, ModeloWorkRevisionsProjection)
        or result.profile_id != client.profile_id
        or result.work_unit_id_filter != selected_id
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return result


def read_modelo_revision_snapshot_for_cli(
    ctx: typer.Context,
    *,
    calculation_revision_id: str | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    selector: ModeloCalculationRevisionSelector,
) -> ModeloWorkRevisionSnapshotProjection:
    """Select once, then read that immutable revision under its own disclosure grant."""
    client, selection = select_modelo_work_revision_for_cli(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        selector=selector,
        default_for=None,
    )
    completed = run_registered_operation(
        client,
        ModeloWorkRevisionSnapshotRequest(
            profile_id=client.profile_id, calculation_revision_id=selection.calculation_revision_id
        ),
        definition_id=MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
        subject_ref=selection.unit.work_unit_id,
        result_type=ModeloWorkRevisionSnapshotProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if (
        not isinstance(result, ModeloWorkRevisionSnapshotProjection)
        or result.profile_id != client.profile_id
        or result.unit.work_unit_id != selection.unit.work_unit_id
        or result.calculation.calculation_revision_id != selection.calculation_revision_id
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return result
