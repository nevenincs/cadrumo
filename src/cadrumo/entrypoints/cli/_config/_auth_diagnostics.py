"""Auth diagnostics CLI command surface."""

from __future__ import annotations

import typer

from ....application.auth import AuthDiagnosticPhoneState
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._command_policy import command_execution_policy
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._execution_policies import ENCRYPTED_READ, ENCRYPTED_WRITE, declare_metadata_group

auth_diagnostics_app = typer.Typer(
    name="diagnostics",
    help=tr("cli.config.auth.diagnostics.help"),
    no_args_is_help=True,
)


@auth_diagnostics_app.command(
    "list",
    help=tr("cli.config.auth.diagnostics.list_help"),
)
@command_execution_policy(ENCRYPTED_READ)
def auth_diagnostics_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """List encrypted auth diagnostics without revealing captured HTML/screenshots."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import list_auth_diagnostics
    from .._config_payloads import AuthDiagnosticsListResult

    report = list_auth_diagnostics()
    lines = [f"row_count\t{report.row_count}"]
    for row in report.rows:
        lines.append(
            "\t".join(
                (
                    row.diagnostic_id or "-",
                    row.captured_at.isoformat(),
                    row.reason,
                    f"mode={row.auth_mode or '-'}",
                    f"identity_kind={row.identity_kind or '-'}",
                    f"profile={row.active_profile_label or row.active_profile_id or '-'}",
                    f"alignment={row.identity_alignment or '-'}",
                    f"headless={row.headless if row.headless is not None else '-'}",
                    f"phone_state={row.phone_state or '-'}",
                    f"html={row.html_captured}",
                    f"screenshot={row.screenshot_captured}",
                ),
            ),
        )
    list_result = AuthDiagnosticsListResult(row_count=report.row_count, rows=list(report.rows))
    _emit_envelope(ctx, command="config.auth.diagnostics.list", result=list_result, lines=lines)


@auth_diagnostics_app.command(
    "show",
    help=tr("cli.config.auth.diagnostics.show_help"),
)
@command_execution_policy(ENCRYPTED_READ)
def auth_diagnostics_show(
    ctx: typer.Context,
    diagnostic_id: str = typer.Argument(..., help=tr("cli.config.auth.diagnostics.id_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Show one encrypted auth diagnostic by id with sensitive bodies redacted."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import load_auth_diagnostic

    detail = load_auth_diagnostic(diagnostic_id)
    if detail is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.diagnostics.not_found",
            context={"diagnostic_id": diagnostic_id},
        )
    from .._config_payloads import AuthDiagnosticsShowResult

    reported_at = detail.phone_state_reported_at.isoformat() if detail.phone_state_reported_at is not None else ""
    observed_at = detail.phone_state_observed_at.isoformat() if detail.phone_state_observed_at is not None else ""
    bool_value = _optional_bool_text
    show_result = AuthDiagnosticsShowResult(**detail.model_dump())
    _emit_envelope(
        ctx,
        command="config.auth.diagnostics.show",
        result=show_result,
        lines=(
            f"diagnostic_id\t{detail.diagnostic_id or diagnostic_id}",
            f"captured_at\t{detail.captured_at.isoformat()}",
            f"reason\t{detail.reason}",
            f"url\t{detail.url}",
            f"auth_mode\t{detail.auth_mode}",
            f"identity_kind\t{detail.identity_kind}",
            f"headless\t{detail.headless if detail.headless is not None else ''}",
            f"active_profile_id\t{detail.active_profile_id}",
            f"active_profile_label\t{detail.active_profile_label}",
            f"active_profile_registered\t{bool_value(detail.active_profile_registered)}",
            f"profile_record_present\t{bool_value(detail.profile_record_present)}",
            f"profile_tax_id_present\t{bool_value(detail.profile_tax_id_present)}",
            f"profile_tax_id_fingerprint\t{detail.profile_tax_id_fingerprint}",
            f"clave_identity_configured\t{bool_value(detail.clave_identity_configured)}",
            f"clave_identity_fingerprint\t{detail.clave_identity_fingerprint}",
            f"identity_alignment\t{detail.identity_alignment}",
            f"dni_fecha_configured\t{bool_value(detail.dni_fecha_configured)}",
            f"dni_fecha_fingerprint\t{detail.dni_fecha_fingerprint}",
            f"nie_soporte_configured\t{bool_value(detail.nie_soporte_configured)}",
            f"nie_soporte_fingerprint\t{detail.nie_soporte_fingerprint}",
            f"certificate_path_configured\t{bool_value(detail.certificate_path_configured)}",
            f"certificate_password_configured\t{bool_value(detail.certificate_password_configured)}",
            f"certificate_file_present\t{bool_value(detail.certificate_file_present)}",
            f"certificate_path_fingerprint\t{detail.certificate_path_fingerprint}",
            f"phone_state\t{detail.phone_state}",
            f"phone_state_source\t{detail.phone_state_source or ''}",
            f"phone_state_observed_at\t{observed_at}",
            f"phone_state_reported_at\t{reported_at}",
            f"operator_report_commands\t{'; '.join(detail.operator_report_commands)}",
            f"html_captured\t{detail.html_captured}",
            f"screenshot_captured\t{detail.screenshot_captured}",
            f"html_excerpt\t{detail.html_excerpt or ''}",
        ),
    )


def _optional_bool_text(value: bool | None) -> str:
    return "" if value is None else str(value)


@auth_diagnostics_app.command(
    "report",
    help=tr(
        "cli.config.auth.diagnostics.report_help",
    ),
)
@command_execution_policy(ENCRYPTED_WRITE)
def auth_diagnostics_report(
    ctx: typer.Context,
    diagnostic_id: str = typer.Argument(..., help=tr("cli.config.auth.diagnostics.id_help")),
    phone_state: AuthDiagnosticPhoneState = typer.Option(
        ...,
        "--phone-state",
        help=tr(
            "cli.config.auth.diagnostics.phone_state_help",
        ),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Record the human-observed Cl@ve app state for a captured diagnostic."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import AUTH_DIAGNOSTIC_PHONE_STATES, record_auth_diagnostic_phone_state

    try:
        result = record_auth_diagnostic_phone_state(diagnostic_id, phone_state)
    except ValueError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.diagnostics.invalid_phone_state",
            context={
                "phone_state": phone_state,
                "choices": ", ".join(AUTH_DIAGNOSTIC_PHONE_STATES),
            },
        ) from exc
    if result is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.diagnostics.not_found",
            context={"diagnostic_id": diagnostic_id},
        )
    from .._config_payloads import AuthDiagnosticsReportResult

    report_result = AuthDiagnosticsReportResult(
        diagnostic_id=result.diagnostic_id,
        phone_state=result.phone_state,
        reported_at=result.reported_at,
    )
    _emit_envelope(
        ctx,
        command="config.auth.diagnostics.report",
        result=report_result,
        lines=(
            f"diagnostic_id\t{result.diagnostic_id}",
            f"phone_state\t{result.phone_state}",
            f"reported_at\t{result.reported_at.isoformat()}",
        ),
    )


declare_metadata_group(auth_diagnostics_app)

__all__ = ["auth_diagnostics_app"]
