"""Registered-operation bridge for the local Modelo 145 CLI commands."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

import typer
from pydantic import ValidationError

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.m145_communication_operation import (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145CommunicationCreateRequest,
    M145CommunicationExportProjection,
    M145CommunicationExportRequest,
    M145CommunicationMarkCompletedRequest,
    M145CommunicationMarkDeliveredRequest,
    M145CommunicationOperationId,
    M145CommunicationOperationRecordNotFoundError,
    M145CommunicationOperationResult,
    M145CommunicationRecordProjection,
    M145CommunicationValidateRequest,
    M145CommunicationValidationProjection,
)
from ...application.modelo.m145_communication_period import M145CommunicationPeriod
from ...application.modelo.m145_communication_records import (
    M145CommunicationExportResult,
    M145CommunicationRecord,
    M145CommunicationRecordAmbiguousError,
    M145CommunicationRecordExportError,
    M145CommunicationRecordTransitionError,
    M145CommunicationRecordValidationError,
    M145CommunicationValidationResult,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.errors.hierarchy import CadrumoError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._modelo_cli_support import parse_casilla_override
from ._modelo_m145_parsing import m145_actor_from_cli, m145_create_command_from_cli
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)

_NOT_FOUND_CODE = M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE


def create_m145_record(
    ctx: typer.Context,
    *,
    year: int,
    period: M145CommunicationPeriod,
    casilla: list[str] | None,
    note: str | None,
    actor: str | None,
) -> M145CommunicationRecord:
    """Create through the retained profile worker and restore its canonical record."""
    client = bound_profile_client(ctx)
    command = m145_create_command_from_cli(
        year=year,
        period=period,
        casilla_specs=casilla,
        note=note,
        parse_casilla_override=parse_casilla_override,
    )
    try:
        request = M145CommunicationCreateRequest.from_command(
            profile_id=client.profile_id,
            command=command,
            actor=_request_actor(actor, client=client),
        )
    except ValidationError as error:
        raise typer.BadParameter(str(error)) from error
    completed = _submit(client, request, definition_id=M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID)
    projection = _completed_result(
        completed,
        profile_id=client.profile_id,
        definition_id=M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
        expected_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED}),
    )
    if not isinstance(projection, M145CommunicationRecordProjection) or projection.state.value != "created":
        _invalid(completed)
    _require_bucket(projection.bucket_id, client, completed)
    return projection.to_record()


def validate_m145_record(
    ctx: typer.Context,
    *,
    communication_record_id: str,
) -> M145CommunicationValidationResult:
    """Run read-only validation on a full communication id or canonical prefix."""
    client = bound_profile_client(ctx)
    request = M145CommunicationValidateRequest(
        profile_id=client.profile_id,
        communication_record_id=communication_record_id,
    )
    completed = _submit(client, request, definition_id=M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID)
    projection = _completed_result(
        completed,
        profile_id=client.profile_id,
        definition_id=M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
        expected_effects=frozenset({OperationEffect.NONE}),
    )
    if not isinstance(projection, M145CommunicationValidationProjection):
        _invalid(completed)
    _require_bucket(projection.bucket_id, client, completed)
    _require_selector_match(projection.communication_record_id, communication_record_id, completed)
    return projection.to_result()


def export_m145_record(
    ctx: typer.Context,
    *,
    communication_record_id: str,
    actor: str | None,
) -> M145CommunicationExportResult:
    """Render and return the local export payload from its encrypted operation result."""
    client = bound_profile_client(ctx)
    request = M145CommunicationExportRequest(
        profile_id=client.profile_id,
        communication_record_id=communication_record_id,
        actor=_request_actor(actor, client=client),
    )
    completed = _submit(client, request, definition_id=M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID)
    projection = _completed_result(
        completed,
        profile_id=client.profile_id,
        definition_id=M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
        expected_effects=frozenset({OperationEffect.UPDATED}),
    )
    if not isinstance(projection, M145CommunicationExportProjection):
        _invalid(completed)
    _require_bucket(projection.bucket_id, client, completed)
    _require_selector_match(projection.communication_record_id, communication_record_id, completed)
    return projection.to_result()


def mark_m145_record_delivered(
    ctx: typer.Context,
    *,
    communication_record_id: str,
    actor: str | None,
) -> M145CommunicationRecord:
    """Mark payer delivery through the registered worker."""
    client = bound_profile_client(ctx)
    request = M145CommunicationMarkDeliveredRequest(
        profile_id=client.profile_id,
        communication_record_id=communication_record_id,
        actor=_request_actor(actor, client=client),
    )
    completed = _submit(client, request, definition_id=M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID)
    projection = _completed_result(
        completed,
        profile_id=client.profile_id,
        definition_id=M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
        expected_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED}),
    )
    if not isinstance(projection, M145CommunicationRecordProjection) or projection.state.value not in {
        "delivered_to_payer",
        "locally_completed",
    }:
        _invalid(completed)
    _require_bucket(projection.bucket_id, client, completed)
    _require_selector_match(projection.communication_record_id, communication_record_id, completed)
    return projection.to_record()


def mark_m145_record_locally_completed(
    ctx: typer.Context,
    *,
    communication_record_id: str,
    actor: str | None,
) -> M145CommunicationRecord:
    """Mark local completion through the registered worker."""
    client = bound_profile_client(ctx)
    request = M145CommunicationMarkCompletedRequest(
        profile_id=client.profile_id,
        communication_record_id=communication_record_id,
        actor=_request_actor(actor, client=client),
    )
    completed = _submit(client, request, definition_id=M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID)
    projection = _completed_result(
        completed,
        profile_id=client.profile_id,
        definition_id=M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
        expected_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED}),
    )
    if not isinstance(projection, M145CommunicationRecordProjection) or projection.state.value != "locally_completed":
        _invalid(completed)
    _require_bucket(projection.bucket_id, client, completed)
    _require_selector_match(projection.communication_record_id, communication_record_id, completed)
    return projection.to_record()


def _request_actor(raw_actor: str | None, *, client: RuntimeFrontendClient) -> str:
    """Keep explicit operator labels and default omitted labels to the bound profile id."""
    return m145_actor_from_cli(raw_actor, resolve_default_actor=lambda: str(client.profile_id))


def _submit(
    client: RuntimeFrontendClient,
    request: (
        M145CommunicationCreateRequest
        | M145CommunicationValidateRequest
        | M145CommunicationExportRequest
        | M145CommunicationMarkDeliveredRequest
        | M145CommunicationMarkCompletedRequest
    ),
    *,
    definition_id: M145CommunicationOperationId,
) -> RegisteredOperationCompletion[M145CommunicationOperationResult]:
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=M145CommunicationOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )


def _completed_result(
    completed: RegisteredOperationCompletion[M145CommunicationOperationResult],
    *,
    profile_id: UUID,
    definition_id: M145CommunicationOperationId,
    expected_effects: frozenset[OperationEffect],
) -> M145CommunicationRecordProjection | M145CommunicationValidationProjection | M145CommunicationExportProjection:
    projection = completed.projection
    if projection.outcome == "prewrite_refusal":
        refusal = projection.refusal
        if (
            refusal is None
            or completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.effect is not OperationEffect.NONE
            or completed.refusal_code != refusal.code
            or projection.profile_id != profile_id
            or projection.operation_id != definition_id
            or projection.result is not None
        ):
            _invalid(completed)
        _raise_canonical_refusal(
            completed,
            refusal.code,
            refusal.message,
            {fact.key: fact.value for fact in refusal.context},
        )
    result = projection.result
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect not in expected_effects
        or projection.outcome != "completed"
        or projection.profile_id != profile_id
        or projection.operation_id != definition_id
        or projection.effect is not completed.effect
        or result is None
    ):
        _invalid(completed)
    expected_kind = {
        M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: "record",
        M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: "validation",
        M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: "export",
        M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: "record",
        M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: "record",
    }[definition_id]
    if result.kind != expected_kind:
        _invalid(completed)
    return result


def _raise_canonical_refusal(
    completed: RegisteredOperationCompletion[M145CommunicationOperationResult],
    code: str,
    message: str,
    context: dict[str, str],
) -> NoReturn:
    errors: dict[str, type[CadrumoError]] = {
        M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE: M145CommunicationOperationRecordNotFoundError,
        "REFUSED_M145_COMMUNICATION_RECORD_AMBIGUOUS": M145CommunicationRecordAmbiguousError,
        "REFUSED_M145_COMMUNICATION_RECORD_VALIDATION": M145CommunicationRecordValidationError,
        "REFUSED_M145_COMMUNICATION_RECORD_EXPORT": M145CommunicationRecordExportError,
        "REFUSED_M145_COMMUNICATION_RECORD_TRANSITION": M145CommunicationRecordTransitionError,
    }
    error_type = errors.get(code)
    if error_type is None:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            refusal_code=code,
        )
    raise error_type(message, context=context)


def _require_bucket(
    bucket_id: str,
    client: RuntimeFrontendClient,
    completed: RegisteredOperationCompletion[M145CommunicationOperationResult],
) -> None:
    if bucket_id != str(client.profile_id):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.UNKNOWN,
        )


def _require_selector_match(
    communication_record_id: str,
    selector: str,
    completed: RegisteredOperationCompletion[M145CommunicationOperationResult],
) -> None:
    if not communication_record_id.startswith(selector.strip()):
        _invalid(completed)


def _invalid(completed: RegisteredOperationCompletion[M145CommunicationOperationResult]) -> NoReturn:
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


__all__ = [
    "create_m145_record",
    "export_m145_record",
    "mark_m145_record_delivered",
    "mark_m145_record_locally_completed",
    "validate_m145_record",
]
