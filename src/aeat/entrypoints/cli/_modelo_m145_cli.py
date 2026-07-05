"""Typer registrations for Modelo 145 local communication commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import typer

from ...application.modelo import (
    M145CommunicationPeriod,
    create_m145_communication_record,
    export_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
    validate_m145_communication_record,
)
from ...core.i18n import tr
from ._common import _emit_envelope
from ._modelo_m145_parsing import ParseCasillaOverride, m145_actor_from_cli, m145_create_command_from_cli
from ._modelo_payloads_m145 import (
    M145CommunicationExportResultPayload,
    M145CommunicationRecordPayload,
    M145CommunicationRecordResult,
    M145CommunicationValidationResultPayload,
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
    app.add_typer(m145_app, name="m145")

    def _bucket_id() -> str:
        require_active_profile()
        return active_bucket_id()

    def _record_result(operation: str, record) -> M145CommunicationRecordResult:
        return M145CommunicationRecordResult(
            operation=operation,
            record=M145CommunicationRecordPayload.from_record(record),
        )

    def _record_lines(operation: str, record) -> list[str]:
        lines = [
            f"operation\t{operation}",
            f"communication_record_id\t{record.communication_record_id}",
            f"bucket_id\t{record.bucket_id}",
            f"modelo\t{record.modelo}",
            f"communication_year\t{record.communication_year}",
            f"period\t{record.period_token.value}",
            f"revision_id\t{record.revision_id}",
            f"state\t{record.state.value}",
            f"created_at\t{record.created_at.isoformat()}",
        ]
        if record.delivered_to_payer_at is not None:
            lines.append(f"delivered_to_payer_at\t{record.delivered_to_payer_at.isoformat()}")
        if record.locally_completed_at is not None:
            lines.append(f"locally_completed_at\t{record.locally_completed_at.isoformat()}")
        if record.note is not None:
            lines.append(f"note\t{record.note}")
        return lines

    @m145_app.command(
        "create",
        help=tr(
            "cli.app.modelo.m145.create_help",
            default="Create a Modelo 145 local payer communication record.",
        ),
    )
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
        operation = "modelo.m145.create"
        _emit_envelope(
            ctx,
            command=operation,
            result=_record_result(operation, record),
            lines=_record_lines(operation, record),
        )

    @m145_app.command(
        "validate",
        help=tr(
            "cli.app.modelo.m145.validate_help",
            default="Validate a Modelo 145 local payer communication record.",
        ),
    )
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
        payload = M145CommunicationValidationResultPayload.from_result(result)
        lines = [
            "operation\tmodelo.m145.validate",
            f"communication_record_id\t{result.communication_record_id}",
            f"valid\t{result.valid}",
            f"issue_count\t{result.issue_count}",
        ]
        for issue in result.issues:
            lines.append(f"issue\t{issue.kind.value}\t{issue.casilla_id or ''}\t{issue.message}")
        _emit_envelope(ctx, command="modelo.m145.validate", result=payload, lines=lines)

    @m145_app.command(
        "export",
        help=tr(
            "cli.app.modelo.m145.export_help",
            default="Export a Modelo 145 local payer communication record.",
        ),
    )
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
            actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
        )
        payload = M145CommunicationExportResultPayload.from_result(result)
        lines = [
            "operation\tmodelo.m145.export",
            f"communication_record_id\t{result.communication_record_id}",
            f"export_layout_id\t{result.export_layout_id}",
            f"encoding\t{result.encoding}",
            f"record_count\t{result.record_count}",
            f"byte_length\t{result.byte_length}",
            f"payload_sha256\t{result.payload_sha256}",
            f"payload_text\t{payload.payload_text}",
        ]
        _emit_envelope(ctx, command="modelo.m145.export", result=payload, lines=lines)

    @m145_app.command(
        "mark-delivered-to-payer",
        help=tr(
            "cli.app.modelo.m145.mark_delivered_to_payer_help",
            default="Mark a Modelo 145 local communication record delivered to the payer.",
        ),
    )
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
            bucket_id=_bucket_id(),
            actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
        )
        operation = "modelo.m145.mark_delivered_to_payer"
        _emit_envelope(
            ctx,
            command=operation,
            result=_record_result(operation, record),
            lines=_record_lines(operation, record),
        )

    @m145_app.command(
        "mark-locally-completed",
        help=tr(
            "cli.app.modelo.m145.mark_locally_completed_help",
            default="Mark a Modelo 145 local communication record locally completed.",
        ),
    )
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
            bucket_id=_bucket_id(),
            actor=m145_actor_from_cli(actor, resolve_default_actor=resolve_default_actor),
        )
        operation = "modelo.m145.mark_locally_completed"
        _emit_envelope(
            ctx,
            command=operation,
            result=_record_result(operation, record),
            lines=_record_lines(operation, record),
        )


__all__ = ["register_m145_communication_commands"]
