"""``aeat auth`` sub-app — authentication provider management (#285).

Kent runs these commands to discover which providers are configured,
sign in, inspect the live session TTL, and clear a persisted session.
The four subcommands are thin dispatch layers over the shared
``AuthProvider`` abstraction in :mod:`aeat.auth`; no auth logic is
reimplemented here.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from ...auth import AuthProviderKind
from ...config import Settings
from ...logging import get_logger
from . import _registry, _session
from ._paths import storage_state_paths
from ._render import (
    render_list_providers_json,
    render_list_providers_table,
    render_no_session_line,
    render_status_json,
    render_status_line,
)

if TYPE_CHECKING:
    from ...auth import AeatSession


logger = get_logger(__name__)

app = typer.Typer(
    name="auth",
    no_args_is_help=True,
    help=("Authentication provider management (#285): list-providers, login, status, logout."),
)

_CONSOLE = Console()


def _load_settings() -> Settings:
    return Settings()


def _parse_kind(raw: str) -> AuthProviderKind:
    try:
        return AuthProviderKind(raw)
    except ValueError as exc:
        valid = ", ".join(k.value for k in AuthProviderKind)
        raise typer.BadParameter(f"unknown provider {raw!r}; valid values: {valid}") from exc


@app.command("list-providers", help="List every known AEAT auth provider and its current state.")
def list_providers(
    configured_only: bool = typer.Option(
        False,
        "--configured",
        help="Filter to providers that are fully configured and available.",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        help="Reserved for future hidden providers; no-op today.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON instead of a pretty table.",
    ),
) -> None:
    """Kent-facing overview of every auth provider in the registry."""
    del show_all  # reserved for future use; see ADR
    settings = _load_settings()

    rows = []
    for entry in _registry.iter_entries():
        description = _registry.describe(entry.kind, settings)
        if configured_only and not description.configured:
            continue
        rows.append((entry, description))

    if json_output:
        typer.echo(json.dumps(render_list_providers_json(rows), indent=2))
        return

    _CONSOLE.print(render_list_providers_table(rows))


def _resolve_kind(
    settings: Settings,
    explicit: AuthProviderKind | None,
) -> AuthProviderKind:
    if explicit is not None:
        return explicit
    try:
        return _registry.default_kind(settings)
    except _registry.NoConfiguredProviderError as exc:
        raise typer.BadParameter(str(exc)) from exc


async def _do_login(settings: Settings, kind: AuthProviderKind) -> AeatSession:
    provider = _registry.build_provider(kind, settings)
    try:
        return await provider.authenticate()
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()


@app.command("login", help="Authenticate with the selected provider and cache the session.")
def login(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Auth provider kind (certificate, clave_permanente, clave_movil, clave_pin).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Refuse to run providers that need a human in the loop (Cl@ve Móvil / Cl@ve PIN).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON instead of a human confirmation line.",
    ),
) -> None:
    """Run the login flow for one provider."""
    settings = _load_settings()
    kind = _resolve_kind(settings, _parse_kind(provider) if provider else None)

    if non_interactive and kind in _registry.INTERACTIVE_KINDS:
        _CONSOLE.print(
            f"[red]provider {kind.value} requires an interactive approval step; cannot run with --non-interactive[/red]"
        )
        raise typer.Exit(code=2)

    try:
        session = asyncio.run(_do_login(settings, kind))
    except _registry.ProviderNotImplementedError as exc:
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        _CONSOLE.print(f"[red]AEAT authentication failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        payload = {
            "provider_kind": session.provider_kind.value,
            "identity_nif": session.identity_nif,
            "authenticated_at": session.authenticated_at.isoformat(),
            "idle_deadline": session.idle_deadline.isoformat(),
            "storage_state_path": str(session.storage_state_path) if session.storage_state_path else None,
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    now = datetime.now(UTC)
    remaining = max(0, int((session.idle_deadline - now).total_seconds() // 60))
    _CONSOLE.print(
        f"[green]signed in as {session.identity_nif} via {session.provider_kind.value}; "
        f"session idle TTL ~{remaining}m[/green]"
    )


@app.command("status", help="Show whether a session is active and how much idle TTL remains.")
def status(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Only report the session for this provider kind.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON instead of a single human-readable line.",
    ),
) -> None:
    """Read persisted session metadata and render the TTL view."""
    settings = _load_settings()
    kind = _parse_kind(provider) if provider else None

    try:
        session = _session.load(settings, kind)
    except _session.CorruptAuthSessionError as exc:
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if session is None or (kind is not None and session.provider_kind != kind):
        if json_output:
            typer.echo(json.dumps({"session": None}, indent=2))
        else:
            _CONSOLE.print(render_no_session_line(settings))
        return

    if json_output:
        typer.echo(json.dumps(render_status_json(session), indent=2))
        return

    _CONSOLE.print(render_status_line(session))


@app.command("logout", help="Clear the cached storage_state for the active (or selected) provider.")
def logout(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Only clear the session for this provider kind.",
    ),
    all_providers: bool = typer.Option(
        False,
        "--all",
        help="Clear every registered provider's cached session.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON with the list of removed paths.",
    ),
) -> None:
    """Delete the storage-state + metadata pair for the selected provider(s)."""
    settings = _load_settings()

    removed: list[Path] = []

    if all_providers:
        for entry in _registry.iter_entries():
            removed.extend(_session.delete(settings, entry.kind))
    else:
        target_kind = _parse_kind(provider) if provider else None
        try:
            persisted = _session.load(settings, target_kind)
        except _session.CorruptAuthSessionError:
            persisted = None

        paths = storage_state_paths(settings)
        if target_kind is not None and persisted is not None and persisted.provider_kind != target_kind:
            # The persisted session belongs to a different provider; leave it alone.
            should_delete = False
        elif target_kind is not None:
            should_delete = persisted is not None
        else:
            should_delete = paths.metadata.exists() or paths.storage_state.exists()

        if should_delete:
            removed.extend(_session.delete(settings, target_kind))

    if json_output:
        typer.echo(json.dumps({"removed_paths": [str(p) for p in removed]}, indent=2))
        return

    if not removed:
        _CONSOLE.print("no active session found; nothing to clear")
        return

    for path in removed:
        _CONSOLE.print(f"cleared {path}")


__all__ = ["app"]
