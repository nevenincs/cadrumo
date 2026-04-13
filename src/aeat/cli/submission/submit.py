"""``aeat submission submit`` — live submission gated on an explicit flag."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from aeat.auth import CertificateError, CertificateHealthSeverity
from aeat.auth import health as certificate_health
from aeat.cli.submission._helpers import build_engine, load_draft
from aeat.config import Settings

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
    i_understand_this_is_real: bool = typer.Option(
        False,
        "--i-understand-this-is-real",
        help=("Explicit consent flag required to enter live submission mode. Without this flag the command exits 2."),
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
    """Submit ``draft_path`` to the real AEAT portal — IRREVERSIBLE.

    The command refuses to run unless ``--i-understand-this-is-real``
    is explicitly passed on the command line. Even with the flag set,
    the engine enforces the ``AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION``
    settings gate.
    """
    if not i_understand_this_is_real:
        _CONSOLE.print("[red]refusing:[/red] live submission requires --i-understand-this-is-real on the command line.")
        raise typer.Exit(code=2)

    _enforce_cert_health(settings=Settings(), force_expiring_cert=force_expiring_cert)

    draft = load_draft(draft_path)
    engine = build_engine()
    filing = asyncio.run(engine.submit_draft(draft, dry_run=False, override_confirmation=True))
    _CONSOLE.print(
        f"[green]LIVE submission OK[/green]: submission_id={filing.submission_id} status={filing.status.value}"
    )
