"""Behavior handlers for Modelo 145 local communication commands.

The command group is a thin transport boundary for local payer communication
records. It parses Typer arguments, resolves the active bucket, delegates all
stateful work to the application Modelo 145 service, and emits typed envelopes
through the sibling rendering/payload modules.

See Also:
    :func:`~application.modelo.create_m145_communication_record`
        Application service used by the ``create`` command.
    :func:`~application.modelo.validate_m145_communication_record`
        Application validation service used by the ``validate`` command.
    :func:`~application.modelo.export_m145_communication_record`
        Application export service used by the ``export`` command.
    :func:`~application.modelo.mark_m145_communication_record_delivered_to_payer`
        Local payer-delivery transition wired by this CLI group.
    :mod:`~entrypoints.cli._modelo_m145_parsing`
        CLI-only parsing helpers for casilla assignments and actor labels.
    :mod:`~entrypoints.cli._modelo_m145_rendering`
        Text/JSON envelope emitters for the graph-declared commands.
    :mod:`~entrypoints.cli._modelo_payloads_m145`
        Typed JSON payload schemas declared for Modelo 145 CLI operations.
"""

from __future__ import annotations

import typer

from ...adapters.outbound.aeat.export._registry_record_renderer import RegistryFixedWidthRecordRenderer
from ...application.modelo._m145_communication_records import (
    create_m145_communication_record,
    export_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
    validate_m145_communication_record,
)
from ...application.modelo.m145_communication_period import M145CommunicationPeriod
from ._common import active_bucket_id_or_refuse
from ._modelo_behavior_support import require_active_profile
from ._modelo_cli_support import parse_casilla_override, resolve_default_actor
from ._modelo_m145_parsing import m145_actor_from_cli, m145_create_command_from_cli
from ._modelo_m145_rendering import emit_m145_export_result, emit_m145_record_result, emit_m145_validation_result

__all__ = ["m145_create", "m145_export", "m145_mark_delivered_to_payer", "m145_mark_locally_completed", "m145_validate"]


def _bucket_id() -> str:
    require_active_profile()
    return active_bucket_id_or_refuse()


def m145_create(
    ctx: typer.Context,
    year: int,
    period: M145CommunicationPeriod = M145CommunicationPeriod.COMMUNICATION,
    casilla: list[str] | None = None,
    note: str | None = None,
    actor: str | None = None,
) -> None:
    """Create a bucket-scoped Modelo 145 local communication record."""
    bucket_id = _bucket_id()
    command = m145_create_command_from_cli(
        year=year, period=period, casilla_specs=casilla, note=note, parse_casilla_override=parse_casilla_override
    )
    record = create_m145_communication_record(
        command, bucket_id=bucket_id, actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor)
    )
    emit_m145_record_result(ctx, operation="modelo.m145.create", record=record)


def m145_validate(ctx: typer.Context, communication_record_id: str) -> None:
    """Validate a persisted Modelo 145 local communication record."""
    result = validate_m145_communication_record(communication_record_id, bucket_id=_bucket_id())
    emit_m145_validation_result(ctx, result=result)


def m145_export(ctx: typer.Context, communication_record_id: str, actor: str | None = None) -> None:
    """Export a persisted Modelo 145 local communication record."""
    result = export_m145_communication_record(
        communication_record_id,
        bucket_id=_bucket_id(),
        renderer=RegistryFixedWidthRecordRenderer(),
        actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
    )
    emit_m145_export_result(ctx, result=result)


def m145_mark_delivered_to_payer(ctx: typer.Context, communication_record_id: str, actor: str | None = None) -> None:
    """Mark a Modelo 145 local communication record delivered to the payer."""
    record = mark_m145_communication_record_delivered_to_payer(
        communication_record_id,
        bucket_id=_bucket_id(),
        actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
    )
    emit_m145_record_result(ctx, operation="modelo.m145.mark_delivered_to_payer", record=record)


def m145_mark_locally_completed(ctx: typer.Context, communication_record_id: str, actor: str | None = None) -> None:
    """Mark a Modelo 145 local communication record locally completed."""
    record = mark_m145_communication_record_locally_completed(
        communication_record_id,
        bucket_id=_bucket_id(),
        actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
    )
    emit_m145_record_result(ctx, operation="modelo.m145.mark_locally_completed", record=record)
