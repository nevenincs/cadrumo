"""Live auth preflight rendering helpers for read-only CLI commands."""

from __future__ import annotations

from collections.abc import Callable

import typer

from ...application.auth.operator import build_live_auth_preflight_report
from ...application.auth.operator_results import LiveAuthPreflightReport
from ...core.redaction import redact_for_cli_output


def _metric_line(key: str, value: object) -> str:
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


def _emit_live_auth_preflight(provider: str | None = None) -> None:
    report = build_live_auth_preflight_report(provider)
    for line in _live_auth_preflight_lines(report):
        typer.echo(redact_for_cli_output(line), err=True)


def _live_auth_preflight_lines(report: LiveAuthPreflightReport) -> tuple[str, ...]:
    return (
        _metric_line("auth_preflight", "redacted"),
        _metric_line("auth_provider", report.provider),
        _metric_line("auth_configured", report.configured),
        _metric_line("auth_available", report.available),
        _metric_line("auth_active_profile", "<profile-id>" if report.active_profile else ""),
        _metric_line("auth_active_profile_status", report.active_profile_status),
        _metric_line("auth_active_profile_registered", report.active_profile_registered),
        _metric_line("auth_active_profile_record_present", report.active_profile_record_present),
        _metric_line("auth_profile_tax_id", "present" if report.profile_tax_id_present else "missing"),
        _metric_line("auth_provider_identity", "present" if report.provider_identity_present else "missing"),
        _metric_line("auth_identity_alignment", report.identity_alignment),
        _metric_line("auth_identity_kind", report.identity_kind),
        _metric_line("auth_mode", report.auth_mode),
        _metric_line("auth_prefer_non_qr", report.prefer_non_qr),
        _metric_line("auth_timeout_ms", report.timeout_ms),
        _metric_line("auth_dni_fecha", "present" if report.dni_fecha_configured else "missing"),
        _metric_line("auth_nie_soporte", "present" if report.nie_soporte_configured else "missing"),
        _metric_line("auth_certificate_path", "present" if report.certificate_path_configured else "missing"),
        _metric_line("auth_certificate_file", "present" if report.certificate_file_present else "missing"),
        _metric_line("auth_persisted_session", "present" if report.persisted_session_present else "missing"),
        _metric_line("auth_persisted_session_expired", report.persisted_session_expired),
        _metric_line("auth_persisted_session_state", report.persisted_session_state),
        _metric_line("auth_probe_result", report.probe_result),
    )
