"""Authenticated CLI bridge for the suffered-withholding certificate operations."""

from __future__ import annotations

from typing import Never
from uuid import UUID

import typer
from pydantic import BaseModel

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
)
from ...application.retencion_soportada_certificado.requests import (
    RetencionSoportadaListRequest,
    RetencionSoportadaRecordRequest,
    RetencionSoportadaRemoveRequest,
)
from ...application.retencion_soportada_certificado.results import (
    RetencionSoportadaListProjection,
    RetencionSoportadaMutationProjection,
    RetencionSoportadaRefusalProjection,
    RetencionSoportadaRowProjection,
)
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .retencion_soportada_results import (
    RetencionSoportadaListResult,
    RetencionSoportadaRecordResult,
    RetencionSoportadaRemoveResult,
    RetencionSoportadaRowPayload,
)

_REFUSAL_EFFECTS = frozenset({OperationEffect.NONE, OperationEffect.PARTIAL})
"""A refusal leaves nothing, or only the certificate bytes custody kept before the record was refused."""

_REFUSAL_MESSAGE_LOCALE_KEYS = {
    "own_tax_id": "aggregation.retencion_soportada.errors.own_tax_id",
    "ejercicio_unsupported": "aggregation.retencion_soportada.errors.ejercicio_unsupported",
    "family_not_declared": "aggregation.retencion_soportada.errors.family_not_declared",
    "identity_mismatch": "aggregation.retencion_soportada.errors.identity_mismatch",
    "stale_revision": "aggregation.retencion_soportada.errors.stale_revision",
    "repercutido_exceeds_ingreso_a_cuenta": "aggregation.retencion_soportada.errors.repercutido_exceeds_ingreso",
    "certificate_fingerprint_required": "aggregation.retencion_soportada.errors.certificate_needs_fingerprint",
    "certificate_not_in_custody": "aggregation.retencion_soportada.errors.certificate_not_in_custody",
    "certificate_file_unreadable": "aggregation.retencion_soportada.errors.certificate_file_unreadable",
    "certificate_fingerprint_mismatch": "aggregation.retencion_soportada.errors.certificate_fingerprint_mismatch",
    "taxpayer_tax_id_unknown": "aggregation.retencion_soportada.errors.taxpayer_tax_id_unknown",
    "not_found": "aggregation.retencion_soportada.errors.not_found",
    "validation": "aggregation.retencion_soportada.errors.validation",
    "trabajo_certificate_figure_missing": "aggregation.retencion_soportada.errors.trabajo_certificate_figure_missing",
}


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
        raise InternalInvariantError("suffered-withholding request has no typed profile identity")
    client: FrontendClient = require_profile_client(ctx, expected_profile_id=profile_id)
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
    if getattr(completed.projection, "profile_id", None) != client.profile_id:
        raise invalid_completion_error(completed)
    return completed


def _raise_refusal(
    completed: RegisteredOperationCompletion[RetencionSoportadaMutationProjection],
    refusal: RetencionSoportadaRefusalProjection,
) -> Never:
    message = _REFUSAL_MESSAGE_LOCALE_KEYS.get(refusal.reason)
    if (
        message is None
        or completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect not in _REFUSAL_EFFECTS
        or completed.refusal_code != refusal.code
    ):
        raise invalid_completion_error(completed)
    raise CliRefusedBoundaryError(
        translated_message=message,
        context={
            "operation_id": str(completed.operation_id),
            "terminal_condition": completed.terminal_condition.value,
            "effect": completed.effect.value,
            "refusal_code": refusal.code,
            "reason": refusal.reason,
            "ejercicio": refusal.ejercicio,
        },
    )


def _row_payload(row: RetencionSoportadaRowProjection) -> RetencionSoportadaRowPayload:
    return RetencionSoportadaRowPayload(
        ejercicio=row.ejercicio,
        income_class=row.income_class.value,
        payer_ref=row.payer_ref,
        payer_name=row.payer_legal_name,
        importe_integro_dinerario=row.importe_integro_dinerario.decimal,
        valoracion_especie=row.valoracion_especie.decimal,
        retencion=row.retencion.decimal,
        ingreso_a_cuenta=row.ingreso_a_cuenta.decimal,
        ingreso_a_cuenta_repercutido=row.ingreso_a_cuenta_repercutido.decimal,
        reducciones_aplicables=None if row.reducciones_aplicables is None else row.reducciones_aplicables.decimal,
        gastos_deducibles=None if row.gastos_deducibles is None else row.gastos_deducibles.decimal,
        pago_a_cuenta=row.pago_a_cuenta.decimal,
        origin=row.origin.value,
        evidence_sha256=row.evidence_fingerprint,
        revision_id=row.revision_id,
    )


def _mutation(
    ctx: typer.Context,
    request: RetencionSoportadaRecordRequest | RetencionSoportadaRemoveRequest,
    *,
    definition_id: str,
    outcome: str,
) -> tuple[RegisteredOperationCompletion[RetencionSoportadaMutationProjection], RetencionSoportadaMutationProjection]:
    completed = _run(
        ctx,
        request,
        definition_id=definition_id,
        result_type=RetencionSoportadaMutationProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_refusal(completed, projection.refusal)
    if (
        projection.outcome != outcome
        or projection.count is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return completed, projection


def list_retencion_soportada(
    ctx: typer.Context, request: RetencionSoportadaListRequest
) -> RetencionSoportadaListResult:
    """Read the stored payer records of one ejercicio through the profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
        result_type=RetencionSoportadaListProjection,
        allow_refusal_detail=False,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.ejercicio != request.ejercicio
    ):
        raise invalid_completion_error(completed)
    return RetencionSoportadaListResult(
        bucket_id=str(request.profile_id),
        ejercicio=projection.ejercicio,
        rows=[_row_payload(row) for row in projection.rows],
        count=len(projection.rows),
    )


def record_retencion_soportada(
    ctx: typer.Context, request: RetencionSoportadaRecordRequest
) -> RetencionSoportadaRecordResult:
    """Record or replace one payer certificate through the profile worker."""
    completed, projection = _mutation(
        ctx,
        request,
        definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
        outcome="recorded",
    )
    if projection.row is None or projection.count is None:
        raise invalid_completion_error(completed)
    return RetencionSoportadaRecordResult(
        bucket_id=str(request.profile_id),
        row=_row_payload(projection.row),
        count=projection.count,
    )


def remove_retencion_soportada(
    ctx: typer.Context, request: RetencionSoportadaRemoveRequest
) -> RetencionSoportadaRemoveResult:
    """Remove one payer record through the profile worker."""
    completed, projection = _mutation(
        ctx,
        request,
        definition_id=RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
        outcome="removed",
    )
    if projection.count is None or projection.row is not None:
        raise invalid_completion_error(completed)
    return RetencionSoportadaRemoveResult(
        bucket_id=str(request.profile_id),
        ejercicio=request.ejercicio,
        income_class=request.income_class.value,
        payer_ref=request.payer_ref,
        count=projection.count,
    )


__all__ = ["list_retencion_soportada", "record_retencion_soportada", "remove_retencion_soportada"]
