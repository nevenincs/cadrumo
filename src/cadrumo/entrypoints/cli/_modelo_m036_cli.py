"""Typer registrations for Modelo 036 declarative-recording commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import typer

from ...application.modelo import (
    M036DeclarationCommand,
    M036DeclarationResult,
    list_m036_declarations,
    read_m036_declaration,
    record_m036_declaration,
)
from ...core.i18n import tr
from ...core.parsing import parse_iso8601_date
from ...domain.calculations.registry import CensoModeloEventKind
from ._command_policy import command_execution_policy
from ._common import _emit_envelope
from ._modelo_execution_policies import MODEL_READ, MODEL_WRITE, declare_metadata_group
from ._modelo_payloads_m036 import (
    M036DeclarationListResult,
    M036DeclarationRecordResult,
    M036DeclarationRowPayload,
    M036DeclarationShowResult,
)

# Shared sede-filing option aliases for the modificacion / baja verbs. The alta
# verb carries `default=` fallback copy on the same keys and keeps its own local
# declarations.
_DeclaredOnOpt = Annotated[str, typer.Option("--declared-on", help=tr("cli.app.modelo.m036.declared_on_help"))]
_SedeJustificanteOpt = Annotated[
    str | None, typer.Option("--sede-justificante", help=tr("cli.app.modelo.m036.justificante_help"))
]
_NoteOpt = Annotated[str | None, typer.Option("--note", help=tr("cli.app.modelo.m036.note_help"))]


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
    declare_metadata_group(m036_app)
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
            parsed_declared_on = parse_iso8601_date(declared_on)
            if parsed_declared_on is None:
                raise ValueError
        except ValueError as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.m036.errors.bad_declared_on",
                    value=declared_on,
                    default=f"--declared-on must be an ISO date (YYYY-MM-DD); got {declared_on!r}.",
                ),
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
    @command_execution_policy(MODEL_WRITE)
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
    @command_execution_policy(MODEL_WRITE)
    def m036_modificacion(
        ctx: typer.Context,
        declared_on: _DeclaredOnOpt,
        sede_justificante: _SedeJustificanteOpt = None,
        note: _NoteOpt = None,
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
    @command_execution_policy(MODEL_WRITE)
    def m036_baja(
        ctx: typer.Context,
        declared_on: _DeclaredOnOpt,
        sede_justificante: _SedeJustificanteOpt = None,
        note: _NoteOpt = None,
    ) -> None:
        """Record an M036 baja declaration filed at sede."""
        record_m036(
            ctx,
            event_kind=CensoModeloEventKind.BAJA,
            declared_on=declared_on,
            sede_justificante=sede_justificante,
            note=note,
        )

    _register_m036_readback_commands(
        m036_app,
        require_active_profile=require_active_profile,
        active_bucket_id=active_bucket_id,
    )


def _register_m036_readback_commands(
    m036_app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    active_bucket_id: Callable[[], str],
) -> None:
    """Register the m036 ``list`` / ``view`` read-back commands on ``m036_app``."""

    @m036_app.command(
        "list",
        help=tr(
            "cli.app.modelo.m036.list_help",
            default="List the M036 declarations recorded in the active profile.",
        ),
    )
    @command_execution_policy(MODEL_READ)
    def m036_list(ctx: typer.Context) -> None:
        """List the active profile's recorded M036 declarations."""
        require_active_profile()
        bucket_id = active_bucket_id()
        declarations = list_m036_declarations(bucket_id=bucket_id)
        result = M036DeclarationListResult(
            bucket_id=bucket_id,
            declaration_count=len(declarations),
            declarations=[_declaration_row(declaration) for declaration in declarations],
        )
        lines = [
            "operation\tmodelo.m036.list",
            f"bucket_id\t{bucket_id}",
            f"declaration_count\t{len(declarations)}",
        ]
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
                    ),
                )
                for declaration in declarations
            )
        else:
            lines.append(
                tr(
                    "cli.app.modelo.m036.list_empty",
                    default="No M036 declarations recorded yet.",
                ),
            )
        _emit_envelope(ctx, command="modelo.m036.list", result=result, lines=lines)

    @m036_app.command(
        "view",
        help=tr(
            "cli.app.modelo.m036.view_help",
            default="View one recorded M036 declaration by id (or unambiguous prefix).",
        ),
    )
    @command_execution_policy(MODEL_READ)
    def m036_view(
        ctx: typer.Context,
        declaration_id: Annotated[
            str,
            typer.Argument(
                help=tr(
                    "cli.app.modelo.m036.declaration_id_help",
                    default="The declaration id (or an unambiguous prefix of it) to view.",
                ),
            ),
        ],
    ) -> None:
        """View one recorded M036 declaration in full."""
        require_active_profile()
        bucket_id = active_bucket_id()
        try:
            declaration = read_m036_declaration(declaration_id, bucket_id=bucket_id)
        except KeyError as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.m036.errors.declaration_not_found",
                    value=declaration_id,
                    default=(
                        f"No M036 declaration matches {declaration_id!r}. "
                        "Run 'aeat app modelo m036 list' to see recorded declarations."
                    ),
                ),
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
        _emit_envelope(ctx, command="modelo.m036.view", result=result, lines=lines)


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


__all__ = ["register_m036_commands"]
