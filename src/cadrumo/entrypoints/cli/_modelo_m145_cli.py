"""Behavior handlers for Modelo 145 local communication commands.

The command group is a thin transport boundary for local payer communication
records. It parses Typer arguments, forwards authenticated requests to the
retained profile worker, and emits typed envelopes through sibling renderers.

See Also:
    :mod:`~entrypoints.cli.runtime_modelo_m145_communication`
        Authenticated registered-operation bridge for all five commands.
    :mod:`~entrypoints.cli._modelo_m145_parsing`
        CLI-only parsing helpers for casilla assignments and actor labels.
    :mod:`~entrypoints.cli._modelo_m145_rendering`
        Text/JSON envelope emitters for the graph-declared commands.
    :mod:`~entrypoints.cli._modelo_payloads_m145`
        Typed JSON payload schemas declared for Modelo 145 CLI operations.
"""

from __future__ import annotations

import typer

from ...application.modelo.m145_communication_period import M145CommunicationPeriod
from ._modelo_m145_rendering import emit_m145_export_result, emit_m145_record_result, emit_m145_validation_result
from .runtime_modelo_m145_communication import (
    create_m145_record,
    export_m145_record,
    mark_m145_record_delivered,
    mark_m145_record_locally_completed,
    validate_m145_record,
)

__all__ = ["m145_create", "m145_export", "m145_mark_delivered_to_payer", "m145_mark_locally_completed", "m145_validate"]


def m145_create(
    ctx: typer.Context,
    year: int,
    period: M145CommunicationPeriod = M145CommunicationPeriod.COMMUNICATION,
    casilla: list[str] | None = None,
    note: str | None = None,
    actor: str | None = None,
) -> None:
    """Create a bucket-scoped Modelo 145 local communication record."""
    record = create_m145_record(ctx, year=year, period=period, casilla=casilla, note=note, actor=actor)
    emit_m145_record_result(ctx, operation="modelo.m145.create", record=record)


def m145_validate(ctx: typer.Context, communication_record_id: str) -> None:
    """Validate a persisted Modelo 145 local communication record."""
    result = validate_m145_record(ctx, communication_record_id=communication_record_id)
    emit_m145_validation_result(ctx, result=result)


def m145_export(ctx: typer.Context, communication_record_id: str, actor: str | None = None) -> None:
    """Export a persisted Modelo 145 local communication record."""
    result = export_m145_record(ctx, communication_record_id=communication_record_id, actor=actor)
    emit_m145_export_result(ctx, result=result)


def m145_mark_delivered_to_payer(ctx: typer.Context, communication_record_id: str, actor: str | None = None) -> None:
    """Mark a Modelo 145 local communication record delivered to the payer."""
    record = mark_m145_record_delivered(ctx, communication_record_id=communication_record_id, actor=actor)
    emit_m145_record_result(ctx, operation="modelo.m145.mark_delivered_to_payer", record=record)


def m145_mark_locally_completed(ctx: typer.Context, communication_record_id: str, actor: str | None = None) -> None:
    """Mark a Modelo 145 local communication record locally completed."""
    record = mark_m145_record_locally_completed(ctx, communication_record_id=communication_record_id, actor=actor)
    emit_m145_record_result(ctx, operation="modelo.m145.mark_locally_completed", record=record)
