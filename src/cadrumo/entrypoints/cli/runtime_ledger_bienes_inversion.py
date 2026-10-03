"""Authenticated CLI bridge for the profile-owned bienes-inversión register."""

from __future__ import annotations

from typing import Never
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.bienes_inversion.registered_contracts import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
)
from ...application.bienes_inversion.registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
)
from ...application.bienes_inversion.registered_result_contracts import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
    BienesInversionRefusalProjection,
    BienInversionRecordProjection,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._bienes_inversion_payloads import (
    BienesInversionDeclareResult,
    BienesInversionListResult,
    BienInversionDisposalPayload,
    BienInversionRecordPayload,
)
from .errors import CliRefusedBoundaryError
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def _client(ctx: typer.Context, profile_id: UUID) -> RuntimeFrontendClient:
    return require_profile_client(ctx, expected_profile_id=profile_id)


def _run[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
    allow_refusal_detail: bool,
) -> RegisteredOperationCompletion[ProjectionT]:
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise RuntimeError("bienes-inversión request has no typed profile identity")
    client = _client(ctx, profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=allow_refusal_detail,
    )
    projection_profile_id = getattr(completed.projection, "profile_id", None)
    if projection_profile_id != client.profile_id:
        raise invalid_completion_error(completed)
    return completed


def _raise_refusal(
    completed: RegisteredOperationCompletion[BienesInversionDeclareProjection],
    refusal: BienesInversionRefusalProjection,
) -> Never:
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != refusal.code
    ):
        raise invalid_completion_error(completed)
    context = {
        "operation_id": str(completed.operation_id),
        "terminal_condition": completed.terminal_condition.value,
        "effect": completed.effect.value,
        "refusal_code": refusal.code,
        "reason": refusal.reason,
    }
    if refusal.identifier is not None:
        context["identifier"] = refusal.identifier
    if refusal.missing is not None:
        context["missing"] = refusal.missing
    if refusal.reason == "duplicate_identifier":
        message = "adapters.persistence.profile.bienes_inversion.errors.record_already_exists"
    elif refusal.reason == "disposal_incomplete":
        message = "cli.app.ledger.bienes_inversion.disposal_requires_both"
    elif refusal.code == BIENES_INVERSION_VALIDATION_REFUSAL_CODE:
        message = "errors.refused.refused_profile_bienes_inversion_validation"
    else:
        raise invalid_completion_error(completed)
    raise CliRefusedBoundaryError(translated_message=message, context=context)


def _record_payload(record: BienInversionRecordProjection) -> BienInversionRecordPayload:
    disposal = record.disposal
    return BienInversionRecordPayload(
        identifier=record.identifier,
        description=record.description,
        acquisition_year=record.acquisition_year,
        cuota_soportada=record.cuota_soportada.decimal,
        prorrata_inicial_pct=record.prorrata_inicial_pct.decimal,
        kind=record.kind,
        art108_elegible=record.art108_elegible,
        acquisition_ledger_id=record.acquisition_ledger_id,
        prorrata_sector_id=record.prorrata_sector_id,
        disposal=(
            BienInversionDisposalPayload(year=disposal.year, regime=disposal.regime) if disposal is not None else None
        ),
        deduccion_efectuada=record.deduccion_efectuada.decimal,
        schema_version=record.schema_version,
    )


def read_bienes_inversion_register(
    ctx: typer.Context,
) -> tuple[RegisteredOperationCompletion[BienesInversionListProjection], BienesInversionListResult]:
    """Read the complete selected-profile register through its worker."""
    profile_id = UUID(require_active_bucket_id())
    request = BienesInversionListRequest(profile_id=profile_id)
    completed = _run(
        ctx,
        request,
        definition_id=BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
        result_type=BienesInversionListProjection,
        allow_refusal_detail=False,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    result = BienesInversionListResult(
        bucket_id=str(profile_id),
        rows=[_record_payload(row) for row in projection.rows],
        count=len(projection.rows),
    )
    return completed, result


def declare_bien_inversion(
    ctx: typer.Context,
    *,
    identifier: str,
    description: str,
    acquisition_year: int,
    acquisition_ledger_id: str,
    cuota_soportada: str,
    prorrata_inicial_pct: str,
    kind: str,
    art108_elegible: bool = True,
    prorrata_sector_id: str | None = None,
    disposal_year: int | None = None,
    disposal_regime: str | None = None,
) -> tuple[RegisteredOperationCompletion[BienesInversionDeclareProjection], BienesInversionDeclareResult]:
    """Submit one operator declaration and preserve the established result schema."""
    profile_id = UUID(require_active_bucket_id())
    request = BienesInversionDeclareRequest(
        profile_id=profile_id,
        identifier=identifier,
        description=description,
        acquisition_year=acquisition_year,
        acquisition_ledger_id=acquisition_ledger_id,
        cuota_soportada=PublicDecimal(decimal=cuota_soportada),
        prorrata_inicial_pct=PublicDecimal(decimal=prorrata_inicial_pct),
        kind=kind,
        art108_elegible=art108_elegible,
        prorrata_sector_id=prorrata_sector_id,
        disposal_year=disposal_year,
        disposal_regime=disposal_regime,
    )
    completed = _run(
        ctx,
        request,
        definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
        result_type=BienesInversionDeclareProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_refusal(completed, projection.refusal)
    if (
        projection.outcome != "declared"
        or projection.record is None
        or projection.count is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    result = BienesInversionDeclareResult(
        bucket_id=str(profile_id),
        record=_record_payload(projection.record),
        count=projection.count,
    )
    return completed, result


__all__ = ["declare_bien_inversion", "read_bienes_inversion_register"]
