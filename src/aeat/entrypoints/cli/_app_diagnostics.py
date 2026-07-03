"""CLI commands for the ``aeat app diagnostics`` subcommand group.

Provides the ``run-health`` verb: a local-only, read-only report combining
recent LLM classification/completion run timing (duration, provider, outcome)
with the persisted-AEAT-session staleness probe, so an operator can diagnose a
slow LLM-backed run or a stale/expired auth session without leaving the host
(GitHub issue #407). Never contacts AEAT and never performs a network call;
LLM run telemetry is read from encrypted local secure-object storage and the
auth probe reads only the locally persisted session token's metadata.

This module is the transport adapter over
:func:`~aeat.application.diagnostics_run_health.build_run_health_report`. It
emits :class:`~aeat.entrypoints.cli._diagnostics_payloads.RunHealthResult`
through :func:`_emit_envelope`.
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

import typer

from ...core.i18n import tr
from ._common import _emit_envelope
from ._diagnostics_payloads import LlmRunProviderPayload, RunHealthResult

app = typer.Typer(
    name="diagnostics",
    help=tr("cli.diagnostics.app_help"),
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback()
def _diagnostics_root(ctx: typer.Context) -> None:
    """Render the ``aeat app diagnostics`` group help when invoked bare.

    A real (non-collapsing) group callback is required here: a Typer
    instance carrying exactly one registered command and no callback is
    collapsed by ``typer.main.get_command`` into that bare command, which
    would silently swallow the ``run-health`` verb name as an unexpected
    positional argument. The callback's presence keeps this a genuine
    Click Group even while only one verb is registered.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


def _parse_iso_date(value: str | None, option: str) -> _date | None:
    if value is None:
        return None
    from ...core.parsing import parse_iso8601_date

    try:
        return parse_iso8601_date(value.strip())
    except ValueError as exc:
        from ._common import _bad

        raise _bad(
            tr(
                "cli.diagnostics.run_health.bad_date",
                option=option,
                value=value,
                default=f"{option} must be an ISO date (YYYY-MM-DD); got {value!r}.",
            ),
        ) from exc


@app.command(
    "run-health",
    help=tr(
        "cli.diagnostics.run_health.help",
        default="Report recent local LLM run timing and persisted AEAT session staleness.",
    ),
)
def diagnostics_run_health(
    ctx: typer.Context,
    since: str | None = typer.Option(
        None,
        "--since",
        help=tr(
            "cli.diagnostics.run_health.since_help",
            default="Inclusive lower ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        help=tr(
            "cli.diagnostics.run_health.until_help",
            default="Inclusive upper ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help=tr(
            "cli.diagnostics.run_health.provider_help",
            default="Restrict the LLM run-timing section to this provider label (e.g. claude, antigravity, codex).",
        ),
    ),
) -> None:
    """Report recent local LLM run timing and persisted AEAT session staleness."""
    from ...application.diagnostics_run_health import build_run_health_report
    from ...core.json_contract import Notice, NoticeSeverity

    since_date = _parse_iso_date(since, "--since")
    until_date = _parse_iso_date(until, "--until")

    report = build_run_health_report(since=since_date, until=until_date, provider=provider)

    result = RunHealthResult(
        since=since_date.isoformat() if since_date is not None else None,
        until=until_date.isoformat() if until_date is not None else None,
        llm_providers=[
            LlmRunProviderPayload(
                provider=row.provider,
                runs=row.runs,
                succeeded=row.succeeded,
                failed=row.failed,
                min_duration_ms=row.min_duration_ms,
                max_duration_ms=row.max_duration_ms,
                mean_duration_ms=_optional_decimal_text(row.mean_duration_ms),
            )
            for row in report.llm_providers
        ],
        total_runs=report.total_runs,
        total_succeeded=report.total_succeeded,
        total_failed=report.total_failed,
        has_run_data=report.has_run_data,
        auth_provider=report.auth_provider,
        auth_configured=report.auth_configured,
        persisted_session_present=report.persisted_session_present,
        persisted_session_expired=report.persisted_session_expired,
        persisted_session_state=report.persisted_session_state,
        probe_summary=report.probe_summary,
        session_stale=report.session_stale,
    )

    lines: list[str] = [tr("cli.diagnostics.run_health.header", default="LLM run health:")]
    if not report.has_run_data:
        lines.append(
            tr(
                "cli.diagnostics.run_health.no_run_data",
                default="No LLM run telemetry recorded yet. Run an LLM-assisted classification to populate it.",
            ),
        )
    else:
        for row in report.llm_providers:
            lines.append(
                f"{row.provider}\truns={row.runs}\tok={row.succeeded}\tfailed={row.failed}"
                f"\tmin_ms={row.min_duration_ms}\tmax_ms={row.max_duration_ms}\tmean_ms={row.mean_duration_ms}",
            )
    lines.append(
        tr(
            "cli.diagnostics.run_health.auth_header",
            default="Auth session:",
        ),
    )
    lines.append(f"provider\t{report.auth_provider or '(none configured)'}")
    lines.append(f"persisted_session_present\t{report.persisted_session_present}")
    lines.append(f"persisted_session_expired\t{report.persisted_session_expired}")
    lines.append(f"persisted_session_state\t{report.persisted_session_state}")

    notices: list[Notice] = []
    if report.session_stale:
        notice = Notice(
            severity=NoticeSeverity.WARNING,
            code="diagnostics.run_health.session_stale",
            message=tr(
                "cli.diagnostics.run_health.session_stale_message",
                default="The persisted AEAT session has passed its idle deadline; a live read will re-authenticate.",
            ),
            suggestion="aeat config auth login",
        )
        notices.append(notice)
        lines.append(
            tr(
                "cli.diagnostics.run_health.session_stale_message",
                default="The persisted AEAT session has passed its idle deadline; a live read will re-authenticate.",
            ),
        )
    elif not report.persisted_session_present:
        notice = Notice(
            severity=NoticeSeverity.INFO,
            code="diagnostics.run_health.no_session",
            message=tr(
                "cli.diagnostics.run_health.no_session_message",
                default="No persisted AEAT session found on disk.",
            ),
            suggestion="aeat config auth login",
        )
        notices.append(notice)

    _emit_envelope(ctx, command="diagnostics.run_health", result=result, lines=lines, notices=notices)


def _optional_decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")
