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
from typing import TYPE_CHECKING, Any

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
    help=("Authentication provider management (#285): list-providers, login, status, whoami, logout."),
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


def _resolve_env_file(settings: Settings) -> Path:
    """Return the env file Settings is bound to (``env/.env`` by default)."""
    env_file = settings.model_config.get("env_file")
    if env_file is None:
        raise typer.BadParameter("Settings has no `env_file` configured; cannot write provider configuration.")
    if isinstance(env_file, Path):
        return env_file
    if isinstance(env_file, str):
        return Path(env_file)
    # pydantic-settings accepts lists / tuples of candidate env files;
    # write to the first one that resolves to a concrete string.
    if isinstance(env_file, (list, tuple)):
        for candidate in env_file:
            if isinstance(candidate, Path):
                return candidate
            if isinstance(candidate, str):
                return Path(candidate)
    raise typer.BadParameter(
        f"Settings.env_file has an unsupported shape ({type(env_file).__name__}); "
        "cannot determine where to persist provider configuration."
    )


def _classify_identity_for_cli(raw: str) -> str:
    """Thin wrapper around the Cl@ve identity classifier used for CLI parameter validation."""
    from ...auth._clave_movil import (
        ClaveMovilConfigurationError,
        _classify_identity,
    )

    try:
        return _classify_identity(raw)
    except ClaveMovilConfigurationError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command(
    "configure",
    help=("Persist auth-provider configuration to env/.env without a manual shell export."),
)
def configure(
    provider: str = typer.Option(
        AuthProviderKind.CLAVE_MOVIL.value,
        "--provider",
        "-p",
        help="Provider to configure (currently only clave_movil is supported here).",
    ),
    dni_nie: str | None = typer.Option(
        None,
        "--dni-nie",
        help="Set your Spanish DNI or NIE. The CLI prompts for it when omitted.",
    ),
    dni_fecha: str | None = typer.Option(
        None,
        "--dni-fecha",
        help=(
            "Set the DNI validity date printed on your card (YYYY-MM-DD). "
            "Required only when --prefer-non-qr is used with a DNI identity."
        ),
    ),
    nie_soporte: str | None = typer.Option(
        None,
        "--nie-soporte",
        help=(
            "Set the NIE support number printed on your document. "
            "Required only when --prefer-non-qr is used with a NIE identity."
        ),
    ),
    prefer_non_qr: bool | None = typer.Option(
        None,
        "--prefer-non-qr/--prefer-qr",
        help=(
            "Choose how AEAT triggers the Cl@ve app push. "
            "--prefer-non-qr (default): type DNI/NIE + contraste in the "
            "browser and get a direct push notification on your phone. "
            "--prefer-qr: AEAT displays a QR you scan with the Cl@ve app's "
            "'Scan QR' feature; slightly slower but works when you don't "
            "have your DNI's expiry date handy. Both paths still require "
            "you to approve every login on your phone."
        ),
    ),
    set_default: bool = typer.Option(
        True,
        "--set-default/--no-set-default",
        help="Also set AEAT_AUTH_PROVIDER=<provider> so `aeat auth login` picks this provider by default.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Never prompt. Fail if a required value is missing.",
    ),
) -> None:
    """Write Cl@ve Móvil configuration to ``env/.env`` idempotently.

    Uses the same env-writer as ``aeat setup`` (:func:`aeat.env_io.write_env_vars`),
    so existing comments and unrelated keys are preserved. ``env/.env`` is
    created if missing.
    """
    kind = _parse_kind(provider)
    if kind is not AuthProviderKind.CLAVE_MOVIL:
        raise typer.BadParameter(
            f"`aeat auth configure --provider {provider}` is not supported yet. "
            "Run `aeat setup` for the certificate provider."
        )

    settings = _load_settings()
    env_file = _resolve_env_file(settings)

    if dni_nie is None and not non_interactive:
        _CONSOLE.print(
            "\nConfigure Cl@ve Móvil login for AEAT Sede Electrónica.\n"
            "Every login sends a push notification to the Cl@ve app on your "
            "phone; you tap 'Approve' to sign in. This step only records the "
            "details AEAT needs to trigger that push."
        )

    if dni_nie is None:
        if non_interactive:
            raise typer.BadParameter("--dni-nie is required with --non-interactive")
        dni_nie = typer.prompt("Enter your DNI or NIE").strip().upper()
    else:
        dni_nie = dni_nie.strip().upper()

    identity_kind = _classify_identity_for_cli(dni_nie)

    # Default to the direct-push flow (DNI/NIE + contraste → phone push);
    # the QR flow is the opt-in for operators who don't have the DNI
    # expiry date / NIE support number to hand.
    resolved_prefer_non_qr = True if prefer_non_qr is None else bool(prefer_non_qr)

    if resolved_prefer_non_qr:
        if identity_kind == "DNI" and not dni_fecha:
            if non_interactive:
                raise typer.BadParameter("--dni-fecha is required with --prefer-non-qr for a DNI identity")
            dni_fecha = typer.prompt("Enter the validity date printed on your DNI (YYYY-MM-DD)").strip()
        if identity_kind == "NIE" and not nie_soporte:
            if non_interactive:
                raise typer.BadParameter("--nie-soporte is required with --prefer-non-qr for a NIE identity")
            nie_soporte = typer.prompt("Enter the support number printed on your NIE document").strip()

    from ...env_io import write_env_vars

    mapping: dict[str, str] = {
        "AEAT_CLAVE_MOVIL_DNI_NIE": dni_nie,
        "AEAT_CLAVE_PREFER_NON_QR": "true" if resolved_prefer_non_qr else "false",
    }
    if dni_fecha:
        mapping["AEAT_CLAVE_MOVIL_DNI_FECHA"] = dni_fecha.strip()
    if nie_soporte:
        mapping["AEAT_CLAVE_MOVIL_NIE_SOPORTE"] = nie_soporte.strip()
    if set_default:
        mapping["AEAT_AUTH_PROVIDER"] = kind.value

    write_env_vars(env_file, mapping)
    _CONSOLE.print(
        f"[green]wrote {len(mapping)} keys to {env_file} — run `aeat auth login` to start the Cl@ve Móvil flow.[/green]"
    )
    for key, value in mapping.items():
        _CONSOLE.print(f"  {key}={value}")


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


async def _do_whoami(settings: Settings, kind: AuthProviderKind) -> tuple[AeatSession, Any]:
    """Probe the persisted session for ``kind`` without side effects.

    Uses ``probe_persisted_session()`` on providers that expose one
    (currently Cl@ve Móvil). Falls back to the generic
    ``authenticate() + verify()`` path on providers that do not —
    intended for the certificate provider's resume-from-storage-state
    flow, which is already idempotent. NEVER triggers a fresh login.
    """
    provider = _registry.build_provider(kind, settings)
    try:
        probe = getattr(provider, "probe_persisted_session", None)
        if probe is not None:
            return await probe()
        # Fallback for providers without a dedicated probe method.
        session = await provider.authenticate()
        assertion = await provider.verify(session)
        return session, assertion
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()


@app.command(
    "whoami",
    help="Probe AEAT with the cached session and confirm it unlocks a live surface.",
)
def whoami(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Use only the session for this provider kind.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON with the probe result instead of the human line.",
    ),
) -> None:
    """Re-open the cached session and hit AEAT Sede to confirm it still works."""
    settings = _load_settings()
    explicit = _parse_kind(provider) if provider else None
    try:
        persisted = _session.load(settings, explicit)
    except _session.CorruptAuthSessionError as exc:
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    if persisted is None:
        _CONSOLE.print(render_no_session_line(settings))
        raise typer.Exit(code=1)
    kind = explicit or persisted.provider_kind

    try:
        refreshed, assertion = asyncio.run(_do_whoami(settings, kind))
    except _registry.ProviderNotImplementedError as exc:
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        _CONSOLE.print(f"[red]AEAT probe failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        detail_payload = (
            assertion.assertion_detail.model_dump(mode="json") if assertion.assertion_detail is not None else None
        )
        payload = {
            "provider_kind": refreshed.provider_kind.value,
            "identity_nif": refreshed.identity_nif,
            "authenticated_at": refreshed.authenticated_at.isoformat(),
            "idle_deadline": refreshed.idle_deadline.isoformat(),
            "probe": {
                "target_url": assertion.target_url,
                "status_code": assertion.status_code,
                "is_valid": assertion.is_valid,
                "elapsed_ms": assertion.elapsed_ms,
                "error_message": assertion.error_message,
                "detail": detail_payload,
            },
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    if assertion.is_valid:
        _CONSOLE.print(
            f"[green]session valid: {refreshed.identity_nif} via "
            f"{refreshed.provider_kind.value}; AEAT returned "
            f"HTTP {assertion.status_code} in {assertion.elapsed_ms}ms[/green]"
        )
    else:
        _CONSOLE.print(
            f"[yellow]session stale or revoked: AEAT returned "
            f"HTTP {assertion.status_code}; run `aeat auth login` to reauthenticate[/yellow]"
        )
        raise typer.Exit(code=1)


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
    elif provider is not None:
        target_kind = _parse_kind(provider)
        try:
            persisted = _session.load(settings, target_kind)
        except _session.CorruptAuthSessionError:
            persisted = None
        target_paths = storage_state_paths(settings, target_kind)
        # `--provider` only removes its own files. A mismatched persisted
        # session elsewhere on disk stays where it is.
        if persisted is not None or target_paths.metadata.exists() or target_paths.storage_state.exists():
            removed.extend(_session.delete(settings, target_kind))
    else:
        # No --provider → clear whichever provider currently has a session
        # on disk. This matches Kent's intuition: `aeat auth logout`
        # clears his active session regardless of which provider produced it.
        try:
            persisted = _session.load(settings)
        except _session.CorruptAuthSessionError:
            persisted = None
        if persisted is not None:
            removed.extend(_session.delete(settings, persisted.provider_kind))

    if json_output:
        typer.echo(json.dumps({"removed_paths": [str(p) for p in removed]}, indent=2))
        return

    if not removed:
        _CONSOLE.print("no active session found; nothing to clear")
        return

    for path in removed:
        _CONSOLE.print(f"cleared {path}")


__all__ = ["app"]
