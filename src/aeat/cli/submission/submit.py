"""``aeat submission submit`` — live submission gated on an explicit flag."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from ...auth import AeatAuthenticator
from ...config import Settings
from ...submission import SubmissionError
from ._helpers import build_engine, load_draft

_CONSOLE = Console()


def _enforce_auth_provider_health(
    *,
    settings: Settings,
    force_expiring_cert: bool,
) -> None:
    """Block live submission when the configured auth material is not healthy.

    Skips silently when no certificate is configured (the engine will
    raise its own preflight error). Emits a yellow warning line when
    the cert is in the WARN window. Exits with code 2 on
    CRITICAL/EXPIRED unless ``--force-expiring-cert`` was passed.
    """
    description = AeatAuthenticator(settings).describe()
    if not description.configured:
        return
    if not description.available:
        _CONSOLE.print(
            "[red]refusing:[/red] auth provider health check failed: "
            f"{description.health_summary or 'provider unavailable'}"
        )
        raise typer.Exit(code=2)
    severity = description.health_severity
    days = description.days_until_expiry
    if severity is None or days is None or severity == "OK":
        return
    if severity == "WARN":
        _CONSOLE.print(
            f"[yellow]warning:[/yellow] auth provider nearing expiry "
            f"(severity={severity}, days_until_expiry={days}). Proceeding."
        )
        return
    if force_expiring_cert:
        _CONSOLE.print(
            f"[yellow]override:[/yellow] --force-expiring-cert set; "
            f"proceeding despite severity={severity} "
            f"(days_until_expiry={days})."
        )
        return
    _CONSOLE.print(
        f"[red]refusing:[/red] auth provider severity={severity} "
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
    the engine still owns the env gates, pytest refusal, exact phrase
    confirmation, and live transport checks.
    """
    if not i_understand_this_is_real:
        _CONSOLE.print("[red]refusing:[/red] live submission requires --i-understand-this-is-real on the command line.")
        raise typer.Exit(code=2)

    draft = load_draft(draft_path)
    settings = Settings()
    engine = build_engine(settings)
    if engine.live_transport_supported:
        _enforce_auth_provider_health(settings=settings, force_expiring_cert=force_expiring_cert)
    try:
        filing = asyncio.run(engine.submit_draft(draft, dry_run=False))
    except SubmissionError as exc:
        _CONSOLE.print(f"[red]refusing:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _CONSOLE.print(
        f"[green]LIVE submission OK[/green]: submission_id={filing.submission_id} status={filing.status.value}"
    )
