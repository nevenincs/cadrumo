# ruff: noqa: E501 - localized guidance and tabular wire lines are atomic
"""Behavior handlers for Modelo 036 declarative-recording commands."""

from __future__ import annotations

import typer

from ...application.modelo._m036_lifecycle import (
    M036DeclarationCommand,
    M036DeclarationResult,
    list_m036_declarations,
    read_m036_declaration,
    record_m036_declaration,
)
from ...core.i18n import tr
from ...core.parsing import parse_iso8601_date
from cadrumo.domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ._common import active_bucket_id_or_refuse, emit_envelope
from ._modelo_behavior_support import require_active_profile
from ._modelo_payloads_m036 import (
    M036DeclarationListResult,
    M036DeclarationRecordResult,
    M036DeclarationRowPayload,
    M036DeclarationShowResult,
)


def _declaration_row(declaration: M036DeclarationResult) -> M036DeclarationRowPayload:
    """Project a persisted declaration into its JSON-serialisable row payload."""
    return M036DeclarationRowPayload(
        declaration_id=declaration.declaration_id,
        bucket_id=declaration.bucket_id,
        profile_id=declaration.profile_id,
        event_kind=declaration.event_kind.value,
        declared_on=declaration.declared_on.isoformat(),
        sede_justificante=declaration.sede_justificante,
        note=declaration.note,
        recorded_at=declaration.recorded_at.isoformat(),
    )


__all__ = ["m036_alta", "m036_baja", "m036_list", "m036_modificacion", "m036_view", "record_m036"]


def record_m036(
    ctx: typer.Context,
    *,
    event_kind: CensoModeloEventKind,
    declared_on: str,
    sede_justificante: str | None,
    note: str | None,
) -> None:
    """Shared body for the three m036 declarative verbs."""
    require_active_profile()
    try:
        parsed_declared_on = parse_iso8601_date(declared_on)
        if parsed_declared_on is None:
            raise ValueError
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.m036.errors.bad_declared_on",
                value=declared_on,
                default=f"--declared-on must be an ISO date (YYYY-MM-DD); got {declared_on!r}.",
            )
        ) from exc
    bucket_id = active_bucket_id_or_refuse()
    command = M036DeclarationCommand(
        profile_id=bucket_id,
        event_kind=event_kind,
        declared_on=parsed_declared_on,
        sede_justificante=sede_justificante,
        note=note,
    )
    result = record_m036_declaration(command, bucket_id=bucket_id)
    payload = M036DeclarationRecordResult(
        declaration_id=result.declaration_id,
        bucket_id=result.bucket_id,
        profile_id=result.profile_id,
        event_kind=result.event_kind.value,
        declared_on=result.declared_on.isoformat(),
        sede_justificante=result.sede_justificante,
        recorded_at=result.recorded_at.isoformat(),
    )
    lines = [
        f"declaration_id\t{result.declaration_id}",
        f"event_kind\t{result.event_kind.value}",
        f"declared_on\t{result.declared_on.isoformat()}",
        f"recorded_at\t{result.recorded_at.isoformat()}",
    ]
    if result.sede_justificante is not None:
        lines.append(f"sede_justificante\t{result.sede_justificante}")
    emit_envelope(ctx, command=f"modelo.m036.{result.event_kind.value}", result=payload, lines=lines)


def m036_alta(
    ctx: typer.Context, declared_on: str, sede_justificante: str | None = None, note: str | None = None
) -> None:
    """Record an M036 alta filed through AEAT Sede or in person at a competent AEAT office; the electronic justificante is optional."""
    record_m036(
        ctx,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=declared_on,
        sede_justificante=sede_justificante,
        note=note,
    )


def m036_modificacion(
    ctx: typer.Context,
    declared_on: str,
    sede_justificante: str | None = None,
    note: str | None = None,
) -> None:
    """Record an M036 modificacion filed through AEAT Sede or in person at a competent AEAT office; the electronic justificante is optional."""
    record_m036(
        ctx,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=declared_on,
        sede_justificante=sede_justificante,
        note=note,
    )


def m036_baja(
    ctx: typer.Context,
    declared_on: str,
    sede_justificante: str | None = None,
    note: str | None = None,
) -> None:
    """Record an M036 baja filed through AEAT Sede or in person at a competent AEAT office; the electronic justificante is optional."""
    record_m036(
        ctx,
        event_kind=CensoModeloEventKind.BAJA,
        declared_on=declared_on,
        sede_justificante=sede_justificante,
        note=note,
    )


def m036_list(ctx: typer.Context) -> None:
    """List the active profile's recorded M036 declarations."""
    require_active_profile()
    bucket_id = active_bucket_id_or_refuse()
    declarations = list_m036_declarations(bucket_id=bucket_id)
    result = M036DeclarationListResult(
        bucket_id=bucket_id,
        declaration_count=len(declarations),
        declarations=[_declaration_row(declaration) for declaration in declarations],
    )
    lines = ["operation\tmodelo.m036.list", f"bucket_id\t{bucket_id}", f"declaration_count\t{len(declarations)}"]
    if declarations:
        lines.append("declaration_id\tevent_kind\tdeclared_on\trecorded_at\tjustificante_present")
        lines.extend(
            "\t".join(
                (
                    declaration.declaration_id,
                    declaration.event_kind.value,
                    declaration.declared_on.isoformat(),
                    declaration.recorded_at.isoformat(),
                    "yes" if declaration.sede_justificante is not None else "no",
                )
            )
            for declaration in declarations
        )
    else:
        lines.append(tr("cli.app.modelo.m036.list_empty", default="No M036 declarations recorded yet."))
    emit_envelope(ctx, command="modelo.m036.list", result=result, lines=lines)


def m036_view(ctx: typer.Context, declaration_id: str) -> None:
    """View one recorded M036 declaration in full."""
    require_active_profile()
    bucket_id = active_bucket_id_or_refuse()
    try:
        declaration = read_m036_declaration(declaration_id, bucket_id=bucket_id)
    except KeyError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.m036.errors.declaration_not_found",
                value=declaration_id,
                default=f"No M036 declaration matches {declaration_id!r}. Run 'aeat app modelo m036 list' to see recorded declarations.",
            )
        ) from exc
    result = M036DeclarationShowResult(
        declaration_id=declaration.declaration_id,
        bucket_id=declaration.bucket_id,
        profile_id=declaration.profile_id,
        event_kind=declaration.event_kind.value,
        declared_on=declaration.declared_on.isoformat(),
        sede_justificante=declaration.sede_justificante,
        note=declaration.note,
        recorded_at=declaration.recorded_at.isoformat(),
    )
    lines = [
        "operation\tmodelo.m036.view",
        f"declaration_id\t{declaration.declaration_id}",
        f"event_kind\t{declaration.event_kind.value}",
        f"declared_on\t{declaration.declared_on.isoformat()}",
        f"recorded_at\t{declaration.recorded_at.isoformat()}",
    ]
    if declaration.sede_justificante is not None:
        lines.append(f"sede_justificante\t{declaration.sede_justificante}")
    if declaration.note is not None:
        lines.append(f"note\t{declaration.note}")
    emit_envelope(ctx, command="modelo.m036.view", result=result, lines=lines)
