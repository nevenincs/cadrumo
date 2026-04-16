"""``aeat submission submit`` — live submission gated on an explicit flag."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import typer
from rich.console import Console

from aeat.auth import CertificateError, CertificateHealthSeverity
from aeat.auth import health as certificate_health
from aeat.cli.submission._helpers import build_engine, load_draft
from aeat.config import Settings
from aeat.submission import SubmissionError, SubmissionPreflightError

_CONSOLE = Console()


def _enforce_cert_health(
    *,
    settings: Settings,
    force_expiring_cert: bool,
) -> None:
    """Block live submission when the configured cert is CRITICAL/EXPIRED.

    Skips silently when no certificate is configured (the engine will
    raise its own preflight error). Emits a yellow warning line when
    the cert is in the WARN window. Exits with code 2 on
    CRITICAL/EXPIRED unless ``--force-expiring-cert`` was passed.
    """
    if settings.aeat_certificate_path is None:
        return
    if settings.aeat_certificate_password_secret is None:
        _CONSOLE.print(
            "[red]refusing:[/red] AEAT_CERTIFICATE_PASSWORD_SECRET is not set; "
            "cannot evaluate certificate health for the pre-expiry gate."
        )
        raise typer.Exit(code=2)
    # Bridge pydantic-settings → os.environ for the cert loader.
    # See doctor.check_certificate_health for the same pattern.
    os.environ["AEAT_CERTIFICATE_PASSWORD_SECRET"] = settings.aeat_certificate_password_secret.get_secret_value()
    try:
        result = certificate_health(
            settings.aeat_certificate_path,
            password_env_var="AEAT_CERTIFICATE_PASSWORD_SECRET",  # noqa: S106 - env var NAME, not a secret
            warn_days=settings.aeat_cert_warn_days,
            critical_days=settings.aeat_cert_critical_days,
            friendly_name=settings.aeat_certificate_friendly_name,
            backend=settings.aeat_certificate_backend,
        )
    except CertificateError as exc:
        _CONSOLE.print(f"[red]refusing:[/red] certificate health check failed: {exc.__class__.__name__}: {exc}")
        raise typer.Exit(code=2) from exc
    severity = result.severity
    days = result.days_until_expiry
    if severity is CertificateHealthSeverity.OK:
        return
    if severity is CertificateHealthSeverity.WARN:
        _CONSOLE.print(
            f"[yellow]warning:[/yellow] certificate nearing expiry "
            f"(severity={severity.value}, days_until_expiry={days}). Proceeding."
        )
        return
    if force_expiring_cert:
        _CONSOLE.print(
            f"[yellow]override:[/yellow] --force-expiring-cert set; "
            f"proceeding despite severity={severity.value} "
            f"(days_until_expiry={days})."
        )
        return
    _CONSOLE.print(
        f"[red]refusing:[/red] certificate severity={severity.value} "
        f"(days_until_expiry={days}). Renew the certificate or pass "
        f"--force-expiring-cert to override."
    )
    raise typer.Exit(code=2)


def submit_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a CLI-format draft JSON."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run the submit command in dry-run mode.",
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Attempt a real AEAT submission.",
    ),
    force_expiring_cert: bool = typer.Option(
        False,
        "--force-expiring-cert",
        help=(
            "Bypass the CRITICAL/EXPIRED certificate pre-expiry gate (#94). "
            "Use only when you know the cert is about to be renewed and you "
            "need to file before the renewal completes."
        ),
    ),
) -> None:
    """Submit ``draft_path`` with an explicit ``--dry-run`` or ``--live`` choice."""
    if dry_run == live:
        _CONSOLE.print("[red]refusing:[/red] choose exactly one of --dry-run or --live.")
        raise typer.Exit(code=2)

    draft = load_draft(draft_path)
    engine = build_engine()
    if live and not engine.supports_live_submission():
        _CONSOLE.print(
            "[red]refusing:[/red] live submission is unavailable because this CLI runtime is backed by _NullSession."
        )
        raise typer.Exit(code=2)
    if live:
        _enforce_cert_health(settings=Settings(), force_expiring_cert=force_expiring_cert)

    try:
        filing = asyncio.run(engine.submit_draft(draft, dry_run=dry_run))
    except SubmissionPreflightError as exc:
        _CONSOLE.print(f"[red]refusing:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except SubmissionError as exc:
        _CONSOLE.print(f"[red]failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    mode_label = "dry-run" if dry_run else "LIVE"
    _CONSOLE.print(
        f"[green]{mode_label} submission OK[/green]: submission_id={filing.submission_id} status={filing.status.value}"
    )
