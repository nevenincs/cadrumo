"""Authenticated CLI bridge for the Modelo 232 related-party statement operations."""

from __future__ import annotations

from typing import Final, Never

import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.m232_related_party.contracts import M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID
from ...application.m232_related_party.requests import (
    Modelo232RelatedPartyListRequest,
    Modelo232RelatedPartyWriteRequest,
)
from ...application.m232_related_party.results import (
    Modelo232GroundProjection,
    Modelo232NoneStatementProjection,
    Modelo232OperationProjection,
    Modelo232RelatedPartyListProjection,
    Modelo232RelatedPartyMutationProjection,
    Modelo232RelatedPartyRefusalProjection,
    Modelo232TurnoverStatementProjection,
    Modelo232VerdictProjection,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .m232_related_party_results import (
    Modelo232GroundPayload,
    Modelo232NoneStatementPayload,
    Modelo232OperationPayload,
    Modelo232RelatedPartyListResult,
    Modelo232TurnoverStatementPayload,
    Modelo232VerdictPayload,
)

__all__ = [
    "list_m232_related_party",
    "none_statement_payload",
    "operation_payload",
    "submit_m232_related_party_write",
    "turnover_statement_payload",
]

_MESSAGE_LOCALE_KEYS: Final[dict[str, str]] = {
    "ejercicio_unsupported": "aggregation.modelo_232_related_party.errors.ejercicio_unsupported",
    "code_unknown": "aggregation.modelo_232_related_party.errors.code_unknown",
    "already_stated": "aggregation.modelo_232_related_party.errors.already_stated",
    "not_stated": "aggregation.modelo_232_related_party.errors.not_stated",
    "none_stated": "aggregation.modelo_232_related_party.errors.none_stated",
    "operations_present": "aggregation.modelo_232_related_party.errors.operations_present",
    "specific_operation_required": "aggregation.modelo_232_related_party.errors.specific_operation_required",
    "stale_revision": "aggregation.modelo_232_related_party.errors.stale_revision",
    "validation": "aggregation.modelo_232_related_party.errors.validation",
}
"""The command line's message for each refusal reason; it may name the command's options."""


def _raise_refusal(
    completed: RegisteredOperationCompletion[Modelo232RelatedPartyMutationProjection],
    refusal: Modelo232RelatedPartyRefusalProjection,
) -> Never:
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != refusal.code
    ):
        raise invalid_completion_error(completed)
    raise CliRefusedBoundaryError(
        translated_message=_MESSAGE_LOCALE_KEYS[refusal.reason],
        context={
            "operation_id": str(completed.operation_id),
            "terminal_condition": completed.terminal_condition.value,
            "effect": completed.effect.value,
            "refusal_code": refusal.code,
            "reason": refusal.reason,
            "ejercicio": refusal.ejercicio,
        },
    )


def _instant_fields(
    row: Modelo232OperationProjection | Modelo232NoneStatementProjection | Modelo232TurnoverStatementProjection,
) -> dict[str, object]:
    return {
        "ejercicio": row.ejercicio,
        "state": row.state.value,
        "state_label": row.state_label,
        "stated_at": row.stated_at.isoformat(),
        "withdrawn_at": None if row.withdrawn_at is None else row.withdrawn_at.isoformat(),
        "revision_id": row.revision_id,
    }


def operation_payload(row: Modelo232OperationProjection) -> Modelo232OperationPayload:
    """Present one stated operation without its counterparty's identifier."""
    return Modelo232OperationPayload.model_validate(
        {
            **_instant_fields(row),
            "operation_id": row.operation_id,
            "operation_kind": row.operation_kind.value,
            "operation_kind_label": row.operation_kind_label,
            "counterparty_name": row.counterparty_name,
            "counterparty_country": row.counterparty_country,
            "tipo_vinculacion": row.tipo_vinculacion,
            "tipo_operacion": row.tipo_operacion,
            "valuation_method": row.valuation_method,
            "direction": None if row.direction is None else row.direction.value,
            "direction_label": row.direction_label,
            "specific_operation": row.specific_operation,
            "amount_eur": row.amount_eur.decimal,
            "exclusion": None if row.exclusion is None else row.exclusion.value,
            "exclusion_label": row.exclusion_label,
            "description": row.description,
            "participation_percent": None if row.participation_percent is None else row.participation_percent.decimal,
            "parent_name": row.parent_name,
        }
    )


def none_statement_payload(row: Modelo232NoneStatementProjection) -> Modelo232NoneStatementPayload:
    """Present one "none" statement."""
    return Modelo232NoneStatementPayload.model_validate(
        {**_instant_fields(row), "statement_id": row.statement_id, "note": row.note}
    )


def turnover_statement_payload(row: Modelo232TurnoverStatementProjection) -> Modelo232TurnoverStatementPayload:
    """Present one turnover statement."""
    return Modelo232TurnoverStatementPayload.model_validate(
        {
            **_instant_fields(row),
            "statement_id": row.statement_id,
            "turnover_eur": row.turnover_eur.decimal,
            "source": row.source.value,
            "source_label": row.source_label,
            "source_reference": row.source_reference,
        }
    )


def _ground_payload(ground: Modelo232GroundProjection) -> Modelo232GroundPayload:
    return Modelo232GroundPayload(
        ground=ground.ground.value,
        ground_label=ground.ground_label,
        state=ground.state.value,
        state_label=ground.state_label,
        largest_total_eur=None if ground.largest_total_eur is None else ground.largest_total_eur.decimal,
        limit_eur=None if ground.limit_eur is None else ground.limit_eur.decimal,
    )


def _verdict_payload(verdict: Modelo232VerdictProjection) -> Modelo232VerdictPayload:
    return Modelo232VerdictPayload(
        obligation=verdict.obligation.value,
        obligation_label=verdict.obligation_label,
        basis=verdict.basis.value,
        basis_label=verdict.basis_label,
        grounds=[_ground_payload(ground) for ground in verdict.grounds],
        counted_operations=verdict.counted_operations,
        excluded_operations=verdict.excluded_operations,
        excluded_total_eur=verdict.excluded_total_eur.decimal,
        turnover_eur=None if verdict.turnover_eur is None else verdict.turnover_eur.decimal,
        turnover_source=None if verdict.turnover_source is None else verdict.turnover_source.value,
        note=verdict.note,
    )


def list_m232_related_party(
    ctx: typer.Context, request: Modelo232RelatedPartyListRequest
) -> Modelo232RelatedPartyListResult:
    """Read everything stated for one ejercicio and its verdict through the profile worker."""
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=Modelo232RelatedPartyListProjection,
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
    year = projection.year
    return Modelo232RelatedPartyListResult(
        bucket_id=str(request.profile_id),
        ejercicio=projection.ejercicio,
        guard_revision_id=year.guard_revision_id,
        operations=[operation_payload(row) for row in year.operations],
        none_statements=[none_statement_payload(row) for row in year.none_statements],
        turnover_statements=[turnover_statement_payload(row) for row in year.turnover_statements],
        verdict=None if year.verdict is None else _verdict_payload(year.verdict),
    )


def submit_m232_related_party_write(
    ctx: typer.Context,
    request: Modelo232RelatedPartyWriteRequest,
    *,
    definition_id: str,
    outcome: str,
) -> Modelo232RelatedPartyMutationProjection:
    """Run one statement or withdrawal through the profile worker; a refusal raises its typed boundary error."""
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=Modelo232RelatedPartyMutationProjection,
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
    if (
        projection.outcome != outcome
        or projection.payload is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return projection
