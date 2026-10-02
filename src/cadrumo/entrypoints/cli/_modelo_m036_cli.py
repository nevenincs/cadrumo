"""Behavior handlers for Modelo 036 declarative-recording commands."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.modelo.m036_operation import M036DeclarationSnapshot
from ...core.i18n.render import tr
from ...core.parsing.dates import parse_iso8601_date
from ...domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ._modelo_behavior_support import require_active_profile
from ._modelo_payloads_m036 import (
    M036DeclarationListResult,
    M036DeclarationRecordResult,
    M036DeclarationRowPayload,
    M036DeclarationShowResult,
)
from .common import active_bucket_id_or_refuse, emit_envelope
from .errors import CliRefusedBoundaryError
from .runtime_modelo_m036 import read_modelo_m036, record_modelo_m036


def _declaration_row(declaration: M036DeclarationSnapshot) -> M036DeclarationRowPayload:
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
            )
        ) from exc
    profile_id = UUID(active_bucket_id_or_refuse())
    declaration = record_modelo_m036(
        ctx,
        profile_id=profile_id,
        event_kind=event_kind,
        declared_on=parsed_declared_on,
        sede_justificante=sede_justificante,
        note=note,
    )
    payload = M036DeclarationRecordResult(
        declaration_id=declaration.declaration_id,
        bucket_id=declaration.bucket_id,
        profile_id=declaration.profile_id,
        event_kind=declaration.event_kind.value,
        declared_on=declaration.declared_on.isoformat(),
        sede_justificante=declaration.sede_justificante,
        recorded_at=declaration.recorded_at.isoformat(),
    )
    lines = [
        f"declaration_id\t{declaration.declaration_id}",
        f"event_kind\t{declaration.event_kind.value}",
        f"declared_on\t{declaration.declared_on.isoformat()}",
        f"recorded_at\t{declaration.recorded_at.isoformat()}",
    ]
    if declaration.sede_justificante is not None:
        lines.append(f"sede_justificante\t{declaration.sede_justificante}")
    emit_envelope(ctx, command=f"modelo.m036.{declaration.event_kind.value}", result=payload, lines=lines)


def m036_alta(
    ctx: typer.Context, declared_on: str, sede_justificante: str | None = None, note: str | None = None
) -> None:
    """Record an M036 alta filed through AEAT Sede or in person at a competent AEAT office.

    The electronic justificante is optional.
    """
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
    """Record an M036 modificacion filed through AEAT Sede or in person at a competent AEAT office.

    The electronic justificante is optional.
    """
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
    """Record an M036 baja filed through AEAT Sede or in person at a competent AEAT office.

    The electronic justificante is optional.
    """
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
    profile_id = UUID(active_bucket_id_or_refuse())
    bucket_id = str(profile_id)
    declarations = read_modelo_m036(
        ctx,
        profile_id=profile_id,
        kind="list",
    )
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
        lines.append(
            tr(
                "cli.app.modelo.m036.list_empty",
            )
        )
    emit_envelope(ctx, command="modelo.m036.list", result=result, lines=lines)


def m036_view(ctx: typer.Context, declaration_id: str) -> None:
    """View one recorded M036 declaration in full."""
    require_active_profile()
    profile_id = UUID(active_bucket_id_or_refuse())
    try:
        declarations = read_modelo_m036(
            ctx,
            profile_id=profile_id,
            kind="view",
            declaration_id=declaration_id,
        )
    except CliRefusedBoundaryError as exc:
        context = exc.context
        expected_refusal = {
            "REFUSED_M036_DECLARATION_NOT_FOUND",
            "REFUSED_M036_DECLARATION_AMBIGUOUS",
        }
        if (
            context is None
            or context.get("reason") not in expected_refusal
            or context.get("refusal_code") != context.get("reason")
            or context.get("terminal_condition") != "refused"
            or context.get("effect") != "none"
        ):
            raise
        raise CliRefusedBoundaryError(
            translated_message="cli.app.modelo.m036.errors.declaration_not_found",
            context={**context, "value": declaration_id},
        ) from None
    declaration = declarations[0]
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
