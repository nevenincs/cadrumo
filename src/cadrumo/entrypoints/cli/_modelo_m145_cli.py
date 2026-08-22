"""Typer registrations for Modelo 145 local communication commands.

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
        Text/JSON envelope emitters for the registered commands.
    :mod:`~entrypoints.cli._modelo_payloads_m145`
        Typed JSON payload schemas registered for Modelo 145 CLI operations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import typer

from ...adapters.outbound.aeat.export import RegistryFixedWidthRecordRenderer
from ...application.modelo import (
    M145CommunicationPeriod,
    create_m145_communication_record,
    export_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
    validate_m145_communication_record,
)
from ...core.i18n import tr
from ._command_policy import command_execution_policy
from ._modelo_execution_policies import MODEL_HANDOFF, MODEL_READ, MODEL_WRITE, declare_metadata_group
from ._modelo_m145_parsing import ParseCasillaOverride, m145_actor_from_cli, m145_create_command_from_cli
from ._modelo_m145_rendering import (
    emit_m145_export_result,
    emit_m145_record_result,
    emit_m145_validation_result,
)


def register_m145_communication_commands(
    app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    active_bucket_id: Callable[[], str],
    parse_casilla_override: ParseCasillaOverride,
    resolve_default_actor: Callable[[], str],
) -> None:
    """Register Modelo 145 local communication commands."""
    m145_app = typer.Typer(
        name="m145",
        help=tr(
            "cli.app.modelo.m145.group_help",
            default="Manage Modelo 145 local payer communication records.",
        ),
        no_args_is_help=True,
        add_completion=False,
    )
    declare_metadata_group(m145_app)
    app.add_typer(m145_app, name="m145")

    def _bucket_id() -> str:
        require_active_profile()
        return active_bucket_id()

    @m145_app.command(
        "create",
        help=tr(
            "cli.app.modelo.m145.create_help",
            default="Create a Modelo 145 local payer communication record.",
        ),
    )
    @command_execution_policy(MODEL_WRITE)
    def m145_create(
        ctx: typer.Context,
        year: Annotated[
            int,
            typer.Option(
                "--year",
                help=tr("cli.app.modelo.m145.year_help", default="Communication year."),
            ),
        ],
        period: Annotated[
            M145CommunicationPeriod,
            typer.Option(
                "--period",
                help=tr(
                    "cli.app.modelo.m145.period_help",
                    default="Communication period token: comunicacion or variacion.",
                ),
            ),
        ] = M145CommunicationPeriod.COMMUNICATION,
        casilla: Annotated[
            list[str] | None,
            typer.Option(
                "--casilla",
                help=tr(
                    "cli.app.modelo.m145.casilla_help",
                    default="Repeatable registry field assignment, ID=VALUE.",
                ),
            ),
        ] = None,
        note: Annotated[
            str | None,
            typer.Option("--note", help=tr("cli.app.modelo.m145.note_help", default="Optional operator note.")),
        ] = None,
        actor: Annotated[
            str | None,
            typer.Option("--by", help=tr("cli.app.modelo.m145.actor_help", default="Operator label for the event.")),
        ] = None,
    ) -> None:
        """Create a bucket-scoped Modelo 145 local communication record."""
        bucket_id = _bucket_id()
        command = m145_create_command_from_cli(
            year=year,
            period=period,
            casilla_specs=casilla,
            note=note,
            parse_casilla_override=parse_casilla_override,
        )
        record = create_m145_communication_record(
            command,
            bucket_id=bucket_id,
            actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
        )
        emit_m145_record_result(ctx, operation="modelo.m145.create", record=record)

    @m145_app.command(
        "validate",
        help=tr(
            "cli.app.modelo.m145.validate_help",
            default="Validate a Modelo 145 local payer communication record.",
        ),
    )
    @command_execution_policy(MODEL_READ)
    def m145_validate(
        ctx: typer.Context,
        communication_record_id: Annotated[
            str,
            typer.Argument(
                help=tr(
                    "cli.app.modelo.m145.communication_record_id_help",
                    default="Communication record id or unambiguous prefix.",
                ),
            ),
        ],
    ) -> None:
        """Validate a persisted Modelo 145 local communication record."""
        result = validate_m145_communication_record(communication_record_id, bucket_id=_bucket_id())
        emit_m145_validation_result(ctx, result=result)

    @m145_app.command(
        "export",
        help=tr(
            "cli.app.modelo.m145.export_help",
            default="Export a Modelo 145 local payer communication record.",
        ),
    )
    @command_execution_policy(MODEL_HANDOFF)
    def m145_export(
        ctx: typer.Context,
        communication_record_id: Annotated[
            str,
            typer.Argument(help=tr("cli.app.modelo.m145.communication_record_id_help")),
        ],
        actor: Annotated[
            str | None,
            typer.Option("--by", help=tr("cli.app.modelo.m145.actor_help")),
        ] = None,
    ) -> None:
        """Export a persisted Modelo 145 local communication record."""
        result = export_m145_communication_record(
            communication_record_id,
            bucket_id=_bucket_id(),
            renderer=RegistryFixedWidthRecordRenderer(),
            actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
        )
        emit_m145_export_result(ctx, result=result)

    _register_m145_transition_commands(
        m145_app,
        bucket_id=_bucket_id,
        resolve_default_actor=resolve_default_actor,
    )


def _register_m145_transition_commands(
    m145_app: typer.Typer,
    *,
    bucket_id: Callable[[], str],
    resolve_default_actor: Callable[[], str],
) -> None:
    @m145_app.command(
        "mark-delivered-to-payer",
        help=tr(
            "cli.app.modelo.m145.mark_delivered_to_payer_help",
            default="Mark a Modelo 145 local communication record delivered to the payer.",
        ),
    )
    @command_execution_policy(MODEL_WRITE)
    def m145_mark_delivered_to_payer(
        ctx: typer.Context,
        communication_record_id: Annotated[
            str,
            typer.Argument(help=tr("cli.app.modelo.m145.communication_record_id_help")),
        ],
        actor: Annotated[
            str | None,
            typer.Option("--by", help=tr("cli.app.modelo.m145.actor_help")),
        ] = None,
    ) -> None:
        """Mark a Modelo 145 local communication record delivered to the payer."""
        record = mark_m145_communication_record_delivered_to_payer(
            communication_record_id,
            bucket_id=bucket_id(),
            actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
        )
        emit_m145_record_result(ctx, operation="modelo.m145.mark_delivered_to_payer", record=record)

    @m145_app.command(
        "mark-locally-completed",
        help=tr(
            "cli.app.modelo.m145.mark_locally_completed_help",
            default="Mark a Modelo 145 local communication record locally completed.",
        ),
    )
    @command_execution_policy(MODEL_WRITE)
    def m145_mark_locally_completed(
        ctx: typer.Context,
        communication_record_id: Annotated[
            str,
            typer.Argument(help=tr("cli.app.modelo.m145.communication_record_id_help")),
        ],
        actor: Annotated[
            str | None,
            typer.Option("--by", help=tr("cli.app.modelo.m145.actor_help")),
        ] = None,
    ) -> None:
        """Mark a Modelo 145 local communication record locally completed."""
        record = mark_m145_communication_record_locally_completed(
            communication_record_id,
            bucket_id=bucket_id(),
            actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
        )
        emit_m145_record_result(ctx, operation="modelo.m145.mark_locally_completed", record=record)


__all__ = ["register_m145_communication_commands"]
