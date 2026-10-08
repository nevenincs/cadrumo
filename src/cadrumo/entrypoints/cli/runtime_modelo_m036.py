"""CLI bridge for registered Modelo 036 declaration operations."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

import typer

from ...application.modelo.m036_operation import (
    M036_READ_OPERATION_DEFINITION_ID,
    M036_RECORD_OPERATION_DEFINITION_ID,
    M036DeclarationSnapshot,
    M036ReadProjection,
    M036ReadRequest,
    M036RecordProjection,
    M036RecordRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.censo_modelos import CensoModeloEventKind
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def record_modelo_m036(
    ctx: typer.Context,
    *,
    profile_id: UUID,
    event_kind: CensoModeloEventKind,
    declared_on: date,
    sede_justificante: str | None,
    note: str | None,
) -> M036DeclarationSnapshot:
    """Record an operator's prior external filing through the installed worker."""
    client = bound_profile_client(ctx)
    if client.profile_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    request = M036RecordRequest(
        profile_id=client.profile_id,
        event_kind=event_kind,
        declared_on=declared_on,
        sede_justificante=sede_justificante,
        note=note,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=M036_RECORD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=M036RecordProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if not isinstance(projection, M036RecordProjection):
        raise invalid_completion_error(completed)
    declaration = projection.declaration
    try:
        if _m036_record_receipt_invalid(completed, projection, client.profile_id) or _m036_declaration_invalid(
            declaration, client.profile_id, event_kind, request
        ):
            raise ValueError("Modelo 036 record receipt differs from its request or profile")
    except Exception:
        raise invalid_completion_error(completed) from None
    return declaration


def read_modelo_m036(
    ctx: typer.Context,
    *,
    profile_id: UUID,
    kind: Literal["list", "view"],
    declaration_id: str | None = None,
) -> tuple[M036DeclarationSnapshot, ...]:
    """List or view declarations through the worker's human-readable operation."""
    client = bound_profile_client(ctx)
    if client.profile_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    request = M036ReadRequest(
        profile_id=client.profile_id,
        kind=kind,
        declaration_id=declaration_id,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=M036_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=M036ReadProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if not isinstance(projection, M036ReadProjection):
        raise invalid_completion_error(completed)
    try:
        declarations = projection.declarations
        if _m036_read_receipt_invalid(completed, projection, client.profile_id, kind) or _m036_read_selection_invalid(
            declarations, client.profile_id, kind, declaration_id
        ):
            raise ValueError("Modelo 036 read receipt differs from its request or profile")
    except Exception:
        raise invalid_completion_error(completed) from None
    return declarations


__all__ = ["read_modelo_m036", "record_modelo_m036"]


def _m036_record_receipt_invalid(
    completed: RegisteredOperationCompletion[M036RecordProjection], projection: M036RecordProjection, profile_id: UUID
) -> bool:
    """Require the successful mutation receipt from the bound profile."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or (projection.profile_id != profile_id)
    )


def _m036_declaration_invalid(
    declaration: M036DeclarationSnapshot, profile_id: UUID, event_kind: CensoModeloEventKind, request: M036RecordRequest
) -> bool:
    """Correlate every recorded declaration fact with the submitted request."""
    return (
        declaration.profile_id != str(profile_id)
        or declaration.bucket_id != str(profile_id)
        or declaration.event_kind is not event_kind
        or (declaration.declared_on != request.declared_on)
        or (declaration.sede_justificante != request.sede_justificante)
        or (declaration.note != request.note)
    )


def _m036_read_receipt_invalid(
    completed: RegisteredOperationCompletion[M036ReadProjection],
    projection: M036ReadProjection,
    profile_id: UUID,
    kind: Literal["list", "view"],
) -> bool:
    """Require the successful read receipt from the requested profile."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or (projection.profile_id != profile_id)
        or (projection.kind != kind)
    )


def _m036_read_selection_invalid(
    declarations: tuple[M036DeclarationSnapshot, ...],
    profile_id: UUID,
    kind: Literal["list", "view"],
    declaration_id: str | None,
) -> bool:
    """Require profile-owned declarations and the exact list or view selector."""
    return (
        any(row.profile_id != str(profile_id) or row.bucket_id != str(profile_id) for row in declarations)
        or (kind == "view" and len(declarations) != 1)
        or (kind == "list" and declaration_id is not None)
        or (
            kind == "view"
            and (declaration_id is None or not str(declarations[0].declaration_id).startswith(declaration_id))
        )
    )
