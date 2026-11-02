"""Authenticated CLI bridge for the suffered-withholding absence attestation operations."""

from __future__ import annotations

from typing import Never

import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.aggregation.retencion_soportada_absence_repository import RETENCION_SOPORTADA_ABSENCE_MESSAGE_KEYS
from ...application.retencion_soportada_absence.contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
)
from ...application.retencion_soportada_absence.requests import (
    RetencionSoportadaAbsenceAttestRequest,
    RetencionSoportadaAbsenceListRequest,
    RetencionSoportadaAbsenceRequest,
    RetencionSoportadaAbsenceWithdrawRequest,
)
from ...application.retencion_soportada_absence.results import (
    RetencionSoportadaAbsenceListProjection,
    RetencionSoportadaAbsenceMutationProjection,
    RetencionSoportadaAbsenceProjection,
    RetencionSoportadaAbsenceRefusalProjection,
    RetencionSoportadaAbsenceRowProjection,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .retencion_soportada_absence_results import (
    RetencionSoportadaAbsencePayload,
    RetencionSoportadaAbsenceRowPayload,
    RetencionSoportadaAttestAbsenceResult,
    RetencionSoportadaListAbsencesResult,
    RetencionSoportadaWithdrawAbsenceResult,
)

__all__ = [
    "attest_retencion_soportada_absence",
    "list_retencion_soportada_absences",
    "withdraw_retencion_soportada_absence",
]


def _raise_refusal(
    completed: RegisteredOperationCompletion[RetencionSoportadaAbsenceMutationProjection],
    refusal: RetencionSoportadaAbsenceRefusalProjection,
) -> Never:
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != refusal.code
    ):
        raise invalid_completion_error(completed)
    raise CliRefusedBoundaryError(
        translated_message=RETENCION_SOPORTADA_ABSENCE_MESSAGE_KEYS[refusal.reason],
        context={
            "operation_id": str(completed.operation_id),
            "terminal_condition": completed.terminal_condition.value,
            "effect": completed.effect.value,
            "refusal_code": refusal.code,
            "reason": refusal.reason,
            "ejercicio": refusal.ejercicio,
            "income_class": refusal.income_class.value,
        },
    )


def _payload(attestation: RetencionSoportadaAbsenceProjection) -> RetencionSoportadaAbsencePayload:
    return RetencionSoportadaAbsencePayload(
        ejercicio=attestation.ejercicio,
        income_class=attestation.income_class.value,
        note=attestation.note,
        state=attestation.state.value,
        attested_at=attestation.attested_at.isoformat(),
        withdrawn_at=None if attestation.withdrawn_at is None else attestation.withdrawn_at.isoformat(),
        revision_id=attestation.revision_id,
    )


def _row_payload(row: RetencionSoportadaAbsenceRowProjection) -> RetencionSoportadaAbsenceRowPayload:
    return RetencionSoportadaAbsenceRowPayload(
        ejercicio=row.ejercicio,
        income_class=row.income_class.value,
        note=row.note,
        state=row.state.value,
        attested_at=row.attested_at.isoformat(),
        withdrawn_at=None if row.withdrawn_at is None else row.withdrawn_at.isoformat(),
        revision_id=row.revision_id,
        income_class_label=row.income_class_label,
    )


def list_retencion_soportada_absences(
    ctx: typer.Context, request: RetencionSoportadaAbsenceListRequest
) -> RetencionSoportadaListAbsencesResult:
    """Read every stored absence attestation of one ejercicio through the profile worker."""
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=RetencionSoportadaAbsenceListProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=False,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.ejercicio != request.ejercicio
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return RetencionSoportadaListAbsencesResult(
        bucket_id=str(request.profile_id),
        ejercicio=projection.ejercicio,
        attestations=[_row_payload(row) for row in projection.attestations],
        count=len(projection.attestations),
    )


def _mutation(
    ctx: typer.Context,
    request: RetencionSoportadaAbsenceRequest,
    *,
    definition_id: str,
    outcome: str,
) -> RetencionSoportadaAbsenceProjection:
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=RetencionSoportadaAbsenceMutationProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.profile_id != client.profile_id or projection.ejercicio != request.ejercicio:
        raise invalid_completion_error(completed)
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_refusal(completed, projection.refusal)
    attestation = projection.attestation
    if (
        projection.outcome != outcome
        or attestation is None
        or attestation.income_class is not request.income_class
        or not _completed_as_update(completed)
    ):
        raise invalid_completion_error(completed)
    return attestation


def _completed_as_update(completed: RegisteredOperationCompletion[RetencionSoportadaAbsenceMutationProjection]) -> bool:
    return (
        completed.terminal_condition is OperationTerminalCondition.SUCCEEDED
        and completed.effect is OperationEffect.UPDATED
        and completed.refusal_code is None
    )


def attest_retencion_soportada_absence(
    ctx: typer.Context, request: RetencionSoportadaAbsenceAttestRequest
) -> RetencionSoportadaAttestAbsenceResult:
    """Attest through the profile worker that no payer withheld on one class in one ejercicio."""
    attestation = _mutation(
        ctx, request, definition_id=RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID, outcome="attested"
    )
    return RetencionSoportadaAttestAbsenceResult(bucket_id=str(request.profile_id), attestation=_payload(attestation))


def withdraw_retencion_soportada_absence(
    ctx: typer.Context, request: RetencionSoportadaAbsenceWithdrawRequest
) -> RetencionSoportadaWithdrawAbsenceResult:
    """Withdraw one active absence attestation through the profile worker."""
    attestation = _mutation(
        ctx, request, definition_id=RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID, outcome="withdrawn"
    )
    return RetencionSoportadaWithdrawAbsenceResult(bucket_id=str(request.profile_id), attestation=_payload(attestation))
