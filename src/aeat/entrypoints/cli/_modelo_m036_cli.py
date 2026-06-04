"""Typer registrations for Modelo 036 declarative-recording commands."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Annotated

import typer

from ...application.modelo import M036DeclarationCommand, record_m036_declaration
from ...core.i18n import tr
from ...domain.calculations.registry import CensoModeloEventKind
from ._common import _emit_envelope
from ._modelo_payloads import M036DeclarationRecordResult


def register_m036_commands(
    app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    active_bucket_id: Callable[[], str],
) -> None:
    """Register Modelo 036 declarative-recording commands."""
    m036_app = typer.Typer(
        name="m036",
        help=tr(
            "cli.app.modelo.m036.group_help",
            default=(
                "Record an M036 declaration filed at sede (alta / modificacion / baja). "
                "The local app never files; AEAT is the authority."
            ),
        ),
        no_args_is_help=True,
        add_completion=False,
    )
    app.add_typer(m036_app, name="m036")

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
            parsed_declared_on = date.fromisoformat(declared_on)
        except ValueError as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.m036.errors.bad_declared_on",
                    value=declared_on,
                    default=f"--declared-on must be an ISO date (YYYY-MM-DD); got {declared_on!r}.",
                )
            ) from exc

        bucket_id = active_bucket_id()
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
        _emit_envelope(ctx, command=f"modelo.m036.{result.event_kind.value}", result=payload, lines=lines)

    @m036_app.command(
        "alta",
        help=tr(
            "cli.app.modelo.m036.alta_help",
            default="Record an M036 alta declaration (initial census registration) filed at sede.",
        ),
    )
    def m036_alta(
        ctx: typer.Context,
        declared_on: Annotated[
            str,
            typer.Option(
                "--declared-on",
                help=tr(
                    "cli.app.modelo.m036.declared_on_help",
                    default="ISO date (YYYY-MM-DD) the operator filed the M036 at sede.",
                ),
            ),
        ],
        sede_justificante: Annotated[
            str | None,
            typer.Option(
                "--sede-justificante",
                help=tr(
                    "cli.app.modelo.m036.justificante_help",
                    default="Optional AEAT acuse de recibo identifier emitted by sede for the filing.",
                ),
            ),
        ] = None,
        note: Annotated[
            str | None,
            typer.Option(
                "--note",
                help=tr("cli.app.modelo.m036.note_help", default="Optional operator note (<= 512 chars)."),
            ),
        ] = None,
    ) -> None:
        """Record an M036 alta declaration filed at sede."""
        record_m036(
            ctx,
            event_kind=CensoModeloEventKind.ALTA,
            declared_on=declared_on,
            sede_justificante=sede_justificante,
            note=note,
        )

    @m036_app.command(
        "modificacion",
        help=tr(
            "cli.app.modelo.m036.modificacion_help",
            default="Record an M036 modificacion declaration (census update) filed at sede.",
        ),
    )
    def m036_modificacion(
        ctx: typer.Context,
        declared_on: Annotated[str, typer.Option("--declared-on", help=tr("cli.app.modelo.m036.declared_on_help"))],
        sede_justificante: Annotated[
            str | None,
            typer.Option("--sede-justificante", help=tr("cli.app.modelo.m036.justificante_help")),
        ] = None,
        note: Annotated[
            str | None,
            typer.Option("--note", help=tr("cli.app.modelo.m036.note_help")),
        ] = None,
    ) -> None:
        """Record an M036 modificacion declaration filed at sede."""
        record_m036(
            ctx,
            event_kind=CensoModeloEventKind.MODIFICACION,
            declared_on=declared_on,
            sede_justificante=sede_justificante,
            note=note,
        )

    @m036_app.command(
        "baja",
        help=tr(
            "cli.app.modelo.m036.baja_help",
            default="Record an M036 baja declaration (census deregistration) filed at sede.",
        ),
    )
    def m036_baja(
        ctx: typer.Context,
        declared_on: Annotated[str, typer.Option("--declared-on", help=tr("cli.app.modelo.m036.declared_on_help"))],
        sede_justificante: Annotated[
            str | None,
            typer.Option("--sede-justificante", help=tr("cli.app.modelo.m036.justificante_help")),
        ] = None,
        note: Annotated[
            str | None,
            typer.Option("--note", help=tr("cli.app.modelo.m036.note_help")),
        ] = None,
    ) -> None:
        """Record an M036 baja declaration filed at sede."""
        record_m036(
            ctx,
            event_kind=CensoModeloEventKind.BAJA,
            declared_on=declared_on,
            sede_justificante=sede_justificante,
            note=note,
        )


__all__ = ["register_m036_commands"]
