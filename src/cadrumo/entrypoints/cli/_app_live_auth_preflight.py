"""Live auth preflight rendering helpers for read-only CLI commands."""

from __future__ import annotations

from collections.abc import Callable

import typer

from ...application.auth.operator import build_live_auth_preflight_report
from ...application.auth.operator_results import LiveAuthPreflightReport
from ...core.redaction.rules import redact_for_cli_output


def metric_line(key: str, value: object) -> str:
    return f"{key}={value}"


def run_auth_preflight(preflight: Callable[[], None] | None, *, family: str) -> None:
    """Run a live command family's registered auth preflight, or refuse if unregistered.

    Single canonical guard shared by the live command-family modules
    (expedientes, justificante, notifications), which previously each
    declared an identical guard differing only in the family name.
    """
    if preflight is None:
        raise RuntimeError(f"live {family} commands were not registered")
    preflight()


def resolve_active_bucket(active_bucket_id: Callable[[], str] | None, *, family: str) -> str:
    """Resolve a live command family's registered active-bucket id, or refuse if unregistered.

    Single canonical guard shared by the live command-family modules
    (expedientes, justificante, notifications, verify), which previously each
    declared an identical guard differing only in the family name.
    """
    if active_bucket_id is None:
        raise RuntimeError(f"live {family} commands were not registered")
    return active_bucket_id()


def emit_live_auth_preflight(provider: str | None = None) -> None:
    report = build_live_auth_preflight_report(provider)
    for line in _live_auth_preflight_lines(report):
        typer.echo(redact_for_cli_output(line), err=True)


def _live_auth_preflight_lines(report: LiveAuthPreflightReport) -> tuple[str, ...]:
    return (
        metric_line("auth_preflight", "redacted"),
        metric_line("auth_provider", report.provider),
        metric_line("auth_configured", report.configured),
        metric_line("auth_available", report.available),
        metric_line("auth_active_profile", "<profile-id>" if report.active_profile else ""),
        metric_line("auth_active_profile_status", report.active_profile_status),
        metric_line("auth_active_profile_registered", report.active_profile_registered),
        metric_line("auth_active_profile_record_present", report.active_profile_record_present),
        metric_line("auth_profile_tax_id", "present" if report.profile_tax_id_present else "missing"),
        metric_line("auth_provider_identity", "present" if report.provider_identity_present else "missing"),
        metric_line("auth_identity_alignment", report.identity_alignment),
        metric_line("auth_identity_kind", report.identity_kind),
        metric_line("auth_mode", report.auth_mode),
        metric_line("auth_prefer_non_qr", report.prefer_non_qr),
        metric_line("auth_timeout_ms", report.timeout_ms),
        metric_line("auth_dni_fecha", "present" if report.dni_fecha_configured else "missing"),
        metric_line("auth_nie_soporte", "present" if report.nie_soporte_configured else "missing"),
        metric_line("auth_certificate_path", "present" if report.certificate_path_configured else "missing"),
        metric_line("auth_certificate_file", "present" if report.certificate_file_present else "missing"),
        metric_line("auth_persisted_session", "present" if report.persisted_session_present else "missing"),
        metric_line("auth_persisted_session_expired", report.persisted_session_expired),
        metric_line("auth_persisted_session_state", report.persisted_session_state),
        metric_line("auth_probe_result", report.probe_result),
    )
