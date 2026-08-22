"""CLI commands for the ``aeat app diagnostics`` subcommand group.

Provides the ``run-health``, ``runs``, ``latency``, ``errors``, and
``llm-usage`` verbs: local-only, read-only reports over recent LLM
classification/completion run timing (duration, provider, outcome), so an
operator can diagnose a slow LLM-backed run, a stale/expired auth session, or
a recurring failure mode without leaving the host.
``run-health`` folds the run telemetry with the persisted-AEAT-session
staleness probe into one aggregate-by-provider report; ``runs`` lists the
individual recorded runs, most-recent-first; ``latency`` reports P50/P95/P99
duration percentiles overall and per provider; ``errors`` breaks down failed
runs by provider and ``error_kind``; ``llm-usage`` reports run counts,
durations, and success rate grouped by provider and, within each provider, by
model. None of the five verbs ever contacts AEAT or performs a network call;
LLM run telemetry is read from encrypted local secure-object storage and the
auth probe reads only the locally persisted session token's metadata.

This module is the transport adapter over
:func:`~application.diagnostics_run_health.build_run_health_report`,
:func:`~application.diagnostics_run_health.list_recent_runs`,
:func:`~application.diagnostics_run_health.build_latency_report`,
:func:`~application.diagnostics_run_health.build_error_breakdown`, and
:func:`~application.diagnostics_run_health.build_llm_usage_report`. It
emits :class:`~entrypoints.cli._diagnostics_payloads.RunHealthResult`,
:class:`~entrypoints.cli._diagnostics_payloads.RunsListResult`,
:class:`~entrypoints.cli._diagnostics_payloads.LatencyResult`,
:class:`~entrypoints.cli._diagnostics_payloads.ErrorsBreakdownResult`,
and :class:`~entrypoints.cli._diagnostics_payloads.LlmUsageResult`
through :func:`_emit_envelope`.

See Also:
    :mod:`~application.diagnostics_run_health`
        Application service layer that builds the local-only diagnostic
        reports exposed by this CLI group.
    :mod:`~entrypoints.cli._diagnostics_payloads`
        Typed JSON payload schemas emitted by these diagnostics commands.
    :mod:`~entrypoints.cli._app_diagnostics_telemetry`
        Nested telemetry subcommand group for the default-off remote tier.
    :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`
        Encrypted local run-timing store read by the application diagnostics.
"""

from __future__ import annotations

from datetime import date as _date

import typer

from ...core.i18n import tr
from ._app_diagnostics_telemetry import telemetry_app
from ._app_execution_policies import LOCAL_STORAGE_READ
from ._command_policy import command_execution_policy
from ._common import _emit_envelope, optional_decimal_text
from ._diagnostics_payloads import (
    ErrorKindCountPayload,
    ErrorsBreakdownResult,
    LatencyPercentilesPayload,
    LatencyProviderRowPayload,
    LatencyResult,
    LlmRunHealthProviderPayload,
    LlmRunProviderPayload,
    LlmUsageModelPayload,
    LlmUsageResult,
    RunHealthResult,
    RunRecordPayload,
    RunsListResult,
)

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
    from ._common import _parse_iso_date as _parse_required_iso_date

    return _parse_required_iso_date(
        value,
        label=option,
        translation_key="cli.diagnostics.run_health.bad_date",
        default=f"{option} must be an ISO date (YYYY-MM-DD); got {value!r}.",
    )


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
                mean_duration_ms=optional_decimal_text(row.mean_duration_ms),
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
        )
        notices.append(notice)

    _emit_envelope(ctx, command="diagnostics.run_health", result=result, lines=lines, notices=notices)


@app.command(
    "runs",
    help=tr(
        "cli.diagnostics.runs.help",
        default="List recent local LLM run-timing records, most-recent-first.",
    ),
)
def diagnostics_runs(
    ctx: typer.Context,
    since: str | None = typer.Option(
        None,
        "--since",
        help=tr(
            "cli.diagnostics.runs.since_help",
            default="Inclusive lower ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        help=tr(
            "cli.diagnostics.runs.until_help",
            default="Inclusive upper ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help=tr(
            "cli.diagnostics.runs.provider_help",
            default="Restrict the listing to this provider label (e.g. claude, antigravity, codex).",
        ),
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        min=1,
        help=tr(
            "cli.diagnostics.runs.limit_help",
            default="Cap the listing to this many most-recent runs.",
        ),
    ),
) -> None:
    """List recent local LLM run-timing records, most-recent-first."""
    from ...application.diagnostics_run_health import list_recent_runs
    from ...core.json_contract import Notice, NoticeSeverity

    since_date = _parse_iso_date(since, "--since")
    until_date = _parse_iso_date(until, "--until")

    rows = list_recent_runs(since=since_date, until=until_date, provider=provider, limit=limit)

    result = RunsListResult(
        since=since_date.isoformat() if since_date is not None else None,
        until=until_date.isoformat() if until_date is not None else None,
        provider=provider,
        limit=limit,
        runs=[
            RunRecordPayload(
                run_id=row.run_id,
                caller=row.caller,
                provider=row.provider,
                model=row.model,
                duration_ms=row.duration_ms,
                succeeded=row.succeeded,
                error_kind=row.error_kind,
                started_at=row.started_at,
            )
            for row in rows
        ],
        total_runs=len(rows),
        has_run_data=bool(rows),
    )

    lines: list[str] = [tr("cli.diagnostics.runs.header", default="Recent LLM runs:")]
    if not rows:
        lines.append(
            tr(
                "cli.diagnostics.runs.no_run_data",
                default="No LLM run telemetry recorded yet. Run an LLM-assisted classification to populate it.",
            ),
        )
    else:
        for row in rows:
            outcome = "ok" if row.succeeded else f"failed({row.error_kind})"
            lines.append(
                f"{row.started_at.isoformat()}\t{row.provider}\t{row.caller}\t{outcome}\tduration_ms={row.duration_ms}",
            )

    notices: list[Notice] = []
    if not rows:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="diagnostics.runs.no_run_data",
                message=tr(
                    "cli.diagnostics.runs.no_run_data",
                    default="No LLM run telemetry recorded yet. Run an LLM-assisted classification to populate it.",
                ),
            ),
        )

    _emit_envelope(ctx, command="diagnostics.runs", result=result, lines=lines, notices=notices)


@app.command(
    "latency",
    help=tr(
        "cli.diagnostics.latency.help",
        default="Report P50/P95/P99 duration percentiles over recent local LLM runs.",
    ),
)
def diagnostics_latency(
    ctx: typer.Context,
    since: str | None = typer.Option(
        None,
        "--since",
        help=tr(
            "cli.diagnostics.latency.since_help",
            default="Inclusive lower ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        help=tr(
            "cli.diagnostics.latency.until_help",
            default="Inclusive upper ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help=tr(
            "cli.diagnostics.latency.provider_help",
            default="Restrict the report to this provider label (e.g. claude, antigravity, codex).",
        ),
    ),
) -> None:
    """Report P50/P95/P99 duration percentiles over recent local LLM runs."""
    from ...application.diagnostics_run_health import build_latency_report
    from ...core.json_contract import Notice, NoticeSeverity

    since_date = _parse_iso_date(since, "--since")
    until_date = _parse_iso_date(until, "--until")

    report = build_latency_report(since=since_date, until=until_date, provider=provider)

    result = LatencyResult(
        since=since_date.isoformat() if since_date is not None else None,
        until=until_date.isoformat() if until_date is not None else None,
        provider=provider,
        overall=LatencyPercentilesPayload(
            entries=report.overall.entries,
            min_duration_ms=report.overall.min_duration_ms,
            max_duration_ms=report.overall.max_duration_ms,
            mean_duration_ms=optional_decimal_text(report.overall.mean_duration_ms),
            p50_duration_ms=report.overall.p50_duration_ms,
            p95_duration_ms=report.overall.p95_duration_ms,
            p99_duration_ms=report.overall.p99_duration_ms,
        ),
        by_provider=[
            LatencyProviderRowPayload(
                provider=provider_name,
                percentiles=LatencyPercentilesPayload(
                    entries=percentiles.entries,
                    min_duration_ms=percentiles.min_duration_ms,
                    max_duration_ms=percentiles.max_duration_ms,
                    mean_duration_ms=optional_decimal_text(percentiles.mean_duration_ms),
                    p50_duration_ms=percentiles.p50_duration_ms,
                    p95_duration_ms=percentiles.p95_duration_ms,
                    p99_duration_ms=percentiles.p99_duration_ms,
                ),
            )
            for provider_name, percentiles in report.by_provider
        ],
        has_run_data=report.has_run_data,
    )

    lines: list[str] = [tr("cli.diagnostics.latency.header", default="LLM run latency:")]
    notices: list[Notice] = []
    if not report.has_run_data:
        message = tr(
            "cli.diagnostics.latency.no_run_data",
            default="No LLM run telemetry recorded yet. Run an LLM-assisted classification to populate it.",
        )
        lines.append(message)
        notices.append(Notice(severity=NoticeSeverity.INFO, code="diagnostics.latency.no_run_data", message=message))
    else:
        overall = report.overall
        lines.append(
            f"overall\tentries={overall.entries}\tp50_ms={overall.p50_duration_ms}"
            f"\tp95_ms={overall.p95_duration_ms}\tp99_ms={overall.p99_duration_ms}"
            f"\tmin_ms={overall.min_duration_ms}\tmax_ms={overall.max_duration_ms}\tmean_ms={overall.mean_duration_ms}",
        )
        for row in result.by_provider:
            percentiles = row.percentiles
            lines.append(
                f"{row.provider}\tentries={percentiles.entries}\tp50_ms={percentiles.p50_duration_ms}"
                f"\tp95_ms={percentiles.p95_duration_ms}\tp99_ms={percentiles.p99_duration_ms}"
                f"\tmin_ms={percentiles.min_duration_ms}\tmax_ms={percentiles.max_duration_ms}"
                f"\tmean_ms={percentiles.mean_duration_ms}",
            )

    _emit_envelope(ctx, command="diagnostics.latency", result=result, lines=lines, notices=notices)


@app.command(
    "errors",
    help=tr(
        "cli.diagnostics.errors.help",
        default="Break down recent failed local LLM runs by provider and error kind.",
    ),
)
def diagnostics_errors(
    ctx: typer.Context,
    since: str | None = typer.Option(
        None,
        "--since",
        help=tr(
            "cli.diagnostics.errors.since_help",
            default="Inclusive lower ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        help=tr(
            "cli.diagnostics.errors.until_help",
            default="Inclusive upper ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help=tr(
            "cli.diagnostics.errors.provider_help",
            default="Restrict the breakdown to this provider label (e.g. claude, antigravity, codex).",
        ),
    ),
) -> None:
    """Break down recent failed local LLM runs by provider and error kind."""
    from ...application.diagnostics_run_health import build_error_breakdown
    from ...core.json_contract import Notice, NoticeSeverity

    since_date = _parse_iso_date(since, "--since")
    until_date = _parse_iso_date(until, "--until")

    report = build_error_breakdown(since=since_date, until=until_date, provider=provider)

    result = ErrorsBreakdownResult(
        since=since_date.isoformat() if since_date is not None else None,
        until=until_date.isoformat() if until_date is not None else None,
        provider=provider,
        total_runs=report.total_runs,
        total_failed=report.total_failed,
        by_error_kind=[
            ErrorKindCountPayload(error_kind=row.error_kind, provider=row.provider, count=row.count)
            for row in report.by_error_kind
        ],
        has_failures=report.has_failures,
    )

    lines: list[str] = [tr("cli.diagnostics.errors.header", default="LLM run errors:")]
    notices: list[Notice] = []
    if not report.has_failures:
        message = tr(
            "cli.diagnostics.errors.no_failures",
            default="No failed LLM runs recorded in this range.",
        )
        lines.append(message)
        notices.append(Notice(severity=NoticeSeverity.INFO, code="diagnostics.errors.no_failures", message=message))
    else:
        for row in result.by_error_kind:
            lines.append(f"{row.provider}\t{row.error_kind}\tcount={row.count}")

    _emit_envelope(ctx, command="diagnostics.errors", result=result, lines=lines, notices=notices)


@app.command(
    "llm-usage",
    help=tr(
        "cli.diagnostics.llm_usage.help",
        default="Report LLM run-usage totals (counts, durations, success rate) by provider and model.",
    ),
)
def diagnostics_llm_usage(
    ctx: typer.Context,
    since: str | None = typer.Option(
        None,
        "--since",
        help=tr(
            "cli.diagnostics.llm_usage.since_help",
            default="Inclusive lower ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        help=tr(
            "cli.diagnostics.llm_usage.until_help",
            default="Inclusive upper ISO date (YYYY-MM-DD) bound on LLM run records.",
        ),
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help=tr(
            "cli.diagnostics.llm_usage.provider_help",
            default="Restrict the summary to this provider label (e.g. claude, antigravity, codex).",
        ),
    ),
) -> None:
    """Report LLM run-usage totals (counts, durations, success rate) by provider and model."""
    from ...application.diagnostics_run_health import build_llm_usage_report
    from ...core.json_contract import Notice, NoticeSeverity

    since_date = _parse_iso_date(since, "--since")
    until_date = _parse_iso_date(until, "--until")

    report = build_llm_usage_report(since=since_date, until=until_date, provider=provider)

    result = LlmUsageResult(
        since=since_date.isoformat() if since_date is not None else None,
        until=until_date.isoformat() if until_date is not None else None,
        provider=provider,
        by_provider=[
            LlmRunHealthProviderPayload(
                provider=row.provider,
                runs=row.runs,
                succeeded=row.succeeded,
                failed=row.failed,
                min_duration_ms=row.min_duration_ms,
                max_duration_ms=row.max_duration_ms,
                mean_duration_ms=optional_decimal_text(row.mean_duration_ms),
                total_duration_ms=row.total_duration_ms,
                success_rate=format(row.success_rate, "f"),
                models=[
                    LlmUsageModelPayload(
                        model=model_row.model,
                        runs=model_row.runs,
                        succeeded=model_row.succeeded,
                        failed=model_row.failed,
                        min_duration_ms=model_row.min_duration_ms,
                        max_duration_ms=model_row.max_duration_ms,
                        mean_duration_ms=optional_decimal_text(model_row.mean_duration_ms),
                        total_duration_ms=model_row.total_duration_ms,
                        success_rate=format(model_row.success_rate, "f"),
                    )
                    for model_row in row.models
                ],
            )
            for row in report.by_provider
        ],
        total_runs=report.total_runs,
        total_succeeded=report.total_succeeded,
        total_failed=report.total_failed,
        overall_success_rate=format(report.overall_success_rate, "f"),
        has_run_data=report.has_run_data,
    )

    lines: list[str] = [tr("cli.diagnostics.llm_usage.header", default="LLM run usage:")]
    notices: list[Notice] = []
    if not report.has_run_data:
        message = tr(
            "cli.diagnostics.llm_usage.no_run_data",
            default="No LLM run telemetry recorded yet. Run an LLM-assisted classification to populate it.",
        )
        lines.append(message)
        notices.append(Notice(severity=NoticeSeverity.INFO, code="diagnostics.llm_usage.no_run_data", message=message))
    else:
        for row in result.by_provider:
            lines.append(
                f"{row.provider}\truns={row.runs}\tok={row.succeeded}\tfailed={row.failed}"
                f"\tsuccess_rate={row.success_rate}\ttotal_ms={row.total_duration_ms}\tmean_ms={row.mean_duration_ms}",
            )
            for model_row in row.models:
                lines.append(
                    f"  {model_row.model or '(unknown)'}\truns={model_row.runs}\tok={model_row.succeeded}"
                    f"\tfailed={model_row.failed}\tsuccess_rate={model_row.success_rate}"
                    f"\ttotal_ms={model_row.total_duration_ms}\tmean_ms={model_row.mean_duration_ms}",
                )

    _emit_envelope(ctx, command="diagnostics.llm_usage", result=result, lines=lines, notices=notices)


app.add_typer(telemetry_app, name="telemetry")

for _callback in (
    _diagnostics_root,
    diagnostics_run_health,
    diagnostics_runs,
    diagnostics_latency,
    diagnostics_errors,
    diagnostics_llm_usage,
):
    command_execution_policy(LOCAL_STORAGE_READ)(_callback)
