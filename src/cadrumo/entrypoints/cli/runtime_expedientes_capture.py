"""CLI bridges for exact-profile expedientes capture operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer
from pydantic import BaseModel

from ...application.live.expedientes_capture_operation import (
    EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
    EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
    ExpedientesBulkCapturePublicResultV1,
    ExpedientesBulkCaptureRequest,
    ExpedientesSingleCapturePublicResultV1,
    ExpedientesSingleCaptureRequest,
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
class ExpedientesSingleCaptureRead:
    """Keep the settled receipt with one safe captured snapshot summary."""

    completion: RegisteredOperationCompletion[ExpedientesSingleCapturePublicResultV1]
    projection: ExpedientesSingleCapturePublicResultV1


@dataclass(frozen=True, slots=True)
class ExpedientesBulkCaptureRead:
    """Keep the settled receipt with the bulk summary and failed input rows."""

    completion: RegisteredOperationCompletion[ExpedientesBulkCapturePublicResultV1]
    projection: ExpedientesBulkCapturePublicResultV1


def _invalid_frame[ResultT: BaseModel](
    completed: RegisteredOperationCompletion[ResultT],
) -> CliRefusedBoundaryError:
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def _require_capture_receipt[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> None:
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect not in {OperationEffect.UPDATED, OperationEffect.NONE}
    ):
        raise ValueError("expedientes capture result disagrees with its settled receipt")


def read_expedientes_single_capture_for_cli(
    ctx: typer.Context,
    *,
    profile_id: UUID,
    modelo: str,
    year: int,
) -> ExpedientesSingleCaptureRead:
    """Submit one declaration-register capture to the bound profile worker."""
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ExpedientesSingleCaptureRequest(profile_id=profile_id, modelo=modelo, year=year)
    completed = run_registered_operation(
        client,
        request,
        definition_id=EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=ExpedientesSingleCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ExpedientesSingleCapturePublicResultV1):
            raise ValueError("expedientes single-capture projection has an invalid type")
        if (
            projection.bucket_id != str(profile_id)
            or projection.source_url != f"declarations:modelo={request.modelo}:ejercicio={request.year}"
        ):
            raise ValueError("expedientes single-capture result does not match its submitted scope")
        _require_capture_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return ExpedientesSingleCaptureRead(completion=completed, projection=projection)


def read_expedientes_bulk_capture_for_cli(
    ctx: typer.Context,
    *,
    profile_id: UUID,
    modelos: tuple[str, ...] | None,
    year_from: int,
    year_to: int,
) -> ExpedientesBulkCaptureRead:
    """Submit a year-range declaration-register capture to the profile worker."""
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ExpedientesBulkCaptureRequest(
        profile_id=profile_id,
        modelos=modelos,
        year_from=year_from,
        year_to=year_to,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=ExpedientesBulkCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ExpedientesBulkCapturePublicResultV1):
            raise ValueError("expedientes bulk-capture projection has an invalid type")
        if (
            projection.bucket_id != str(profile_id)
            or projection.year_from != request.year_from
            or projection.year_to != request.year_to
            or (request.modelos is not None and projection.modelos != request.modelos)
            or projection.captured_snapshot_count != len(projection.snapshot_ids)
            or projection.failed_count != len(projection.failures)
        ):
            raise ValueError("expedientes bulk-capture result does not match its submitted scope")
        for failure in projection.failures:
            if not (request.year_from <= failure.year <= request.year_to) or (
                request.modelos is not None and failure.modelo not in request.modelos
            ):
                raise ValueError("expedientes bulk-capture failure is outside its submitted scope")
        _require_capture_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return ExpedientesBulkCaptureRead(completion=completed, projection=projection)


__all__ = [
    "ExpedientesBulkCaptureRead",
    "ExpedientesSingleCaptureRead",
    "read_expedientes_bulk_capture_for_cli",
    "read_expedientes_single_capture_for_cli",
]
