"""``aeat auth`` sub-app — authentication provider management (#285).

Kent runs these commands to discover which providers are configured,
sign in, inspect the live session TTL, and clear a persisted session.
The four subcommands are thin dispatch layers over the shared
``AuthProvider`` abstraction in :mod:`aeat.adapters.outbound.aeat.auth`; no auth logic is
reimplemented here.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import typer
from pydantic_settings import SettingsConfigDict
from rich.console import Console

from ....adapters.outbound.aeat.auth import (
    AuthProviderKind,
)
from ....adapters.outbound.google import (
    SCOPES,
    GoogleAuthPath,
    get_credentials,
    inspect_google_auth,
)
from ....core.config import PROJECT_ROOT, Settings
from ....core.env_io import write_env_vars
from ....core.logging import get_logger
from ...mcp.launch_google_workspace import ensure_credentials_dir, ensure_project_env_file
from .._errors import CliRefusedBoundaryError, json_output_requested
from .._schemas import OutputRootSchema, OutputSchema, emit_json_success, register_schema
from ..oauth import CREDENTIALS_PAGE_TEMPLATE, REQUIRED_BLOCK, parse_oauth_client_json
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
    from ....adapters.outbound.aeat.auth import AeatSession


logger = get_logger(__name__)

app = typer.Typer(
    name="auth",
    no_args_is_help=True,
    help=(
        "Kent-first auth setup plus AEAT authentication provider management: "
        "init, configure, list-providers, login, status, whoami, logout."
    ),
)

_CONSOLE = Console()


class AuthListProvidersRowJson(OutputSchema):
    """One row from ``aeat auth list-providers --json``."""

    kind: AuthProviderKind
    label: str
    configured: bool
    available: bool
    identity_nif: str | None = None
    subject: str | None = None
    expires_on: date | None = None
    health_severity: str | None = None
    days_until_expiry: int | None = None
    health_summary: str | None = None
    implemented: bool


@register_schema("auth list-providers")
class AuthListProvidersJson(OutputRootSchema[list[AuthListProvidersRowJson]]):
    """Schema for ``aeat auth list-providers --json``."""


@register_schema("auth login")
class AuthLoginJson(OutputSchema):
    """Schema for ``aeat auth login --json``."""

    provider_kind: AuthProviderKind
    identity_nif: str
    authenticated_at: datetime
    idle_deadline: datetime


class AuthStatusNoSessionJson(OutputSchema):
    """No-session payload for ``aeat auth status --json``."""

    session: Literal[None]


class AuthStatusSessionJson(OutputSchema):
    """Active-session payload for ``aeat auth status --json``."""

    provider_kind: AuthProviderKind
    authenticated_at: datetime
    idle_deadline: datetime
    identity_nif: str
    storage_state_path: str
    is_expired: bool
    seconds_remaining: int
    idle_ttl_seconds: int


@register_schema("auth status")
class AuthStatusJson(OutputRootSchema[AuthStatusNoSessionJson | AuthStatusSessionJson]):
    """Schema for ``aeat auth status --json``."""


class AuthWhoamiProbeJson(OutputSchema):
    """Probe details for ``aeat auth whoami --json``."""

    target_url: str
    status_code: int | None = None
    is_valid: bool
    elapsed_ms: int | None = None
    error_message: str | None = None
    detail: dict[str, object] | None = None


@register_schema("auth whoami")
class AuthWhoamiJson(OutputSchema):
    """Schema for ``aeat auth whoami --json``."""

    provider_kind: AuthProviderKind
    identity_nif: str
    authenticated_at: datetime
    idle_deadline: datetime
    probe: AuthWhoamiProbeJson


@register_schema("auth logout")
class AuthLogoutJson(OutputSchema):
    """Schema for ``aeat auth logout --json``."""

    cleared_providers: list[AuthProviderKind]
    removed_paths: list[str]


def _print_step(
    console: Console,
    title: str,
    *,
    purpose: str,
    action: str,
    source: str,
    browser: str,
    success: str,
    continuation: str,
) -> None:
    console.print(f"[bold]{title}[/bold]")
    console.print(f"Purpose: {purpose}")
    console.print(f"Action: {action}")
    console.print(f"Source: {source}")
    console.print(f"Browser: {browser}")
    console.print(f"Success: {success}")
    console.print(f"Next: {continuation}")
    console.print()


def _copy_oauth_client_json(json_path: Path) -> Path:
    raw = json_path.read_text(encoding="utf-8")
    client_id, client_secret = parse_oauth_client_json(json.loads(raw))
    stable_client_path = PROJECT_ROOT / "env" / "oauth-client.json"
    stable_client_path.parent.mkdir(parents=True, exist_ok=True)
    stable_client_path.write_text(raw, encoding="utf-8")
    write_env_vars(
        PROJECT_ROOT / "env" / ".env",
        {
            "GOOGLE_AUTH_PATH": GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV.value,
            "GOOGLE_OAUTH_CLIENT_ID": client_id,
            "GOOGLE_OAUTH_CLIENT_SECRET": client_secret,
            "GOOGLE_OAUTH_CLIENT_JSON": str(stable_client_path),
        },
    )
    return stable_client_path


def _copy_service_account_json(json_path: Path) -> Path:
    stable_path = PROJECT_ROOT / "env" / "service-account.json"
    stable_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(json_path, stable_path)
    write_env_vars(
        PROJECT_ROOT / "env" / ".env",
        {
            "GOOGLE_AUTH_PATH": GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION.value,
            "GOOGLE_APPLICATION_CREDENTIALS": str(stable_path),
        },
    )
    return stable_path


def _persist_selected_google_path(path: GoogleAuthPath) -> None:
    write_env_vars(PROJECT_ROOT / "env" / ".env", {"GOOGLE_AUTH_PATH": path.value})


def _select_google_auth_path(settings: Settings, requested_path: GoogleAuthPath | None) -> GoogleAuthPath:
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if requested_path is not None:
        return requested_path
    if inspection.active_path is not None:
        return inspection.active_path
    return GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV


def _mcp_credentials_dir() -> Path:
    return PROJECT_ROOT / "env" / "workspace-mcp-credentials"


def _google_settings() -> Settings:
    class ProjectRootSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=PROJECT_ROOT / "env" / ".env",
            env_file_encoding="utf-8",
            env_ignore_empty=True,
        )

    return ProjectRootSettings(aeat_token_dir=PROJECT_ROOT / ".tokens")


def _load_settings() -> Settings:
    return Settings()


def _parse_kind(raw: str) -> AuthProviderKind:
    try:
        return AuthProviderKind(raw)
    except ValueError as exc:
        valid = ", ".join(k.value for k in AuthProviderKind)
        raise typer.BadParameter(f"unknown provider {raw!r}; valid values: {valid}") from exc


@app.command("init", help="Guide Kent through the supported Google authentication paths.")
def init(
    path: GoogleAuthPath | None = typer.Option(
        None,
        "--path",
        help="Choose the active auth path. Defaults to the inferred path or Desktop OAuth local-dev.",
    ),
    json_path: Path | None = typer.Option(
        None,
        "--json",
        help="Downloaded Desktop OAuth client JSON to ingest into env/.env.",
    ),
    service_account_json: Path | None = typer.Option(
        None,
        "--service-account-json",
        help="Service-account JSON key to ingest into env/.env.",
    ),
    acquire_cli_token: bool = typer.Option(
        True,
        "--acquire-cli-token/--no-acquire-cli-token",
        help="Acquire or refresh the repo-local CLI OAuth token for the Desktop OAuth path.",
    ),
    reset_cli_token: bool = typer.Option(
        False,
        "--reset-cli-token/--no-reset-cli-token",
        help="Delete the cached CLI OAuth token first so Desktop OAuth consent is reacquired from scratch.",
    ),
    prepare_mcp: bool = typer.Option(
        True,
        "--prepare-mcp/--no-prepare-mcp",
        help="Create the repo-local MCP credentials directory for the selected path.",
    ),
    run_doctor: bool = typer.Option(
        False,
        "--doctor/--no-doctor",
        help="Run `aeat doctor` after the auth path has been prepared.",
    ),
) -> None:
    """Prepare the selected Google auth path and explain the remaining steps."""

    ensure_project_env_file(PROJECT_ROOT / "env" / ".env", PROJECT_ROOT / "env" / ".env.example")
    console = Console()
    selected_path = _select_google_auth_path(_google_settings(), path)

    if selected_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
        if json_path is not None:
            if not json_path.exists():
                console.print(f"[red]Desktop OAuth client JSON does not exist: {json_path}[/]")
                raise typer.Exit(code=1)
            stable_path = _copy_oauth_client_json(json_path)
            _print_step(
                console,
                "Desktop OAuth client imported",
                purpose="Persist the Desktop OAuth local-dev client in a stable repo-local path.",
                action=f"Imported {json_path} into env/.env and copied it to {stable_path}.",
                source="The JSON comes from Google Cloud Console -> APIs & Services -> Credentials.",
                browser="No browser opens during the import step.",
                success=f"env/oauth-client.json exists and GOOGLE_AUTH_PATH={selected_path.value}.",
                continuation="Continue with the CLI OAuth token step below.",
            )

        inspection = inspect_google_auth(_google_settings(), project_root=PROJECT_ROOT)
        if reset_cli_token and inspection.oauth_token_exists:
            inspection.oauth_token_path.unlink(missing_ok=True)
            inspection = inspect_google_auth(_google_settings(), project_root=PROJECT_ROOT)
            _print_step(
                console,
                "CLI OAuth token reset",
                purpose=(
                    "Force a fresh Desktop OAuth consent flow when the cached "
                    "token no longer carries the required Drive or Workspace scopes."
                ),
                action="The cached CLI OAuth token has been deleted.",
                source="The previous Desktop OAuth local-dev consent flow created the cached token.",
                browser="The next CLI token acquisition step opens a fresh browser consent flow.",
                success="The repo-local CLI token cache is empty and ready for re-consent.",
                continuation="Continue with CLI OAuth token acquisition below.",
            )
        if not inspection.desktop_oauth_complete:
            project = _google_settings().google_cloud_project or "<your-project-id>"
            console.print(
                f"[bold]Open this URL in a browser:[/bold]\n  {CREDENTIALS_PAGE_TEMPLATE.format(project=project)}"
            )
            console.print()
            console.print(REQUIRED_BLOCK)
            _print_step(
                console,
                "Desktop OAuth local-dev setup required",
                purpose=(
                    "Desktop OAuth local-dev is the primary workstation path and "
                    "is required before CLI or MCP Google work can proceed."
                ),
                action=(
                    "Create the Desktop app OAuth client in Cloud Console, "
                    "download the JSON, then re-run this command with --json."
                ),
                source=(
                    "Google Cloud Console -> APIs & Services -> Credentials -> Create credentials -> OAuth client ID."
                ),
                browser=(
                    "Your browser opens the Cloud Console now. No Google consent "
                    "screen opens until the later CLI token step."
                ),
                success="You have a downloaded OAuth client JSON file on disk.",
                continuation="uv run aeat auth init --path desktop-oauth-local-dev --json <downloaded-json>",
            )
            raise typer.Exit(code=1)

        _persist_selected_google_path(selected_path)
        inspection = inspect_google_auth(_google_settings(), project_root=PROJECT_ROOT)

        if inspection.oauth_token_issue is not None and not acquire_cli_token:
            _print_step(
                console,
                "CLI OAuth token needs repair",
                purpose=(
                    "Desktop OAuth local-dev cannot drive CLI or bootstrap work until the repo-local token is usable."
                ),
                action="Rerun this command without --no-acquire-cli-token so the token can be reacquired.",
                source="The current repo-local CLI token cache is incomplete or stale.",
                browser="The repair run opens a fresh browser consent flow if the token must be reacquired.",
                success="The repo-local CLI token cache can be loaded with the required scope set.",
                continuation="uv run aeat auth init --path desktop-oauth-local-dev",
            )
            raise typer.Exit(code=1)

        if acquire_cli_token and inspection.oauth_token_issue is not None:
            if inspection.oauth_token_exists:
                inspection.oauth_token_path.unlink(missing_ok=True)
            _print_step(
                console,
                "CLI OAuth token acquisition",
                purpose=(
                    "The CLI/bootstrap path needs a repo-local OAuth token so "
                    "AEAT commands can call Drive, Sheets, Docs, and Service Usage."
                ),
                action="Continue and complete the Google consent flow in the browser window that opens.",
                source="The Desktop OAuth client already stored in env/.env is reused automatically.",
                browser=(
                    "A local OAuth callback flow opens in your browser and asks you to consent to the requested scopes."
                ),
                success=f"{inspection.oauth_token_path} exists after consent completes.",
                continuation="The command will return here and continue with MCP preparation.",
            )
            _ = get_credentials(_google_settings(), scopes=SCOPES)
            inspection = inspect_google_auth(_google_settings(), project_root=PROJECT_ROOT)

        if prepare_mcp and not inspection.mcp_credentials_dir_exists:
            ensure_credentials_dir(_mcp_credentials_dir())
            inspection = inspect_google_auth(_google_settings(), project_root=PROJECT_ROOT)
            _print_step(
                console,
                "MCP cache preparation",
                purpose=(
                    "The Google Workspace MCP server keeps its refresh material in a repo-local gitignored directory."
                ),
                action="The directory has been created for the selected path.",
                source="No external file is needed for this step.",
                browser="No browser opens during MCP cache preparation.",
                success=f"{_mcp_credentials_dir()} now exists.",
                continuation=(
                    "Launch the Google Workspace MCP server once to finish MCP "
                    "credential preparation, or run just gcloud-auth if you "
                    "still need ADC-backed wrappers."
                ),
            )

        _print_step(
            console,
            "Desktop OAuth local-dev status",
            purpose=(
                "Confirm which remaining step is on the path from local auth to verified CLI/bootstrap readiness."
            ),
            action=(
                "If you rely on the legacy ADC wrapper chain, run just gcloud-auth. "
                "If you need MCP access, launch the Google Workspace MCP server once. "
                "Then verify the current state with aeat doctor."
            ),
            source="This decision depends on whether your workflow still needs the ADC-backed wrapper path.",
            browser="just gcloud-auth opens one or two browser-managed gcloud login flows. aeat doctor does not.",
            success=(
                "Desktop OAuth client material is present, the CLI token is usable, "
                "and the MCP cache directory is prepared for first launch."
            ),
            continuation="uv run aeat doctor",
        )
    else:
        if service_account_json is not None:
            if not service_account_json.exists():
                console.print(f"[red]Service-account key does not exist: {service_account_json}[/]")
                raise typer.Exit(code=1)
            stable_path = _copy_service_account_json(service_account_json)
            _print_step(
                console,
                "Service-account key imported",
                purpose="Persist the Service-account automation key in a stable repo-local path.",
                action=f"Imported {service_account_json} into env/.env and copied it to {stable_path}.",
                source="The JSON key comes from Google Cloud Console -> IAM & Admin -> Service Accounts.",
                browser="No browser opens during the import step.",
                success=f"{stable_path} exists and GOOGLE_AUTH_PATH={selected_path.value}.",
                continuation="Continue with MCP preparation or final verification.",
            )

        inspection = inspect_google_auth(_google_settings(), project_root=PROJECT_ROOT)
        if inspection.service_account_existing_path is None:
            _print_step(
                console,
                "Service-account automation setup required",
                purpose="Service-account automation is the headless path for CI and background execution.",
                action=(
                    "Create or locate the service-account key JSON, then re-run "
                    "this command with --service-account-json."
                ),
                source="Google Cloud Console -> IAM & Admin -> Service Accounts -> Keys.",
                browser="No browser consent flow should occur on the service-account path.",
                success="A readable service-account JSON key exists on disk.",
                continuation=(
                    "uv run aeat auth init --path service-account-automation --service-account-json <downloaded-json>"
                ),
            )
            raise typer.Exit(code=1)

        _persist_selected_google_path(selected_path)
        inspection = inspect_google_auth(_google_settings(), project_root=PROJECT_ROOT)

        if prepare_mcp and not inspection.mcp_credentials_dir_exists:
            ensure_credentials_dir(_mcp_credentials_dir())

        _print_step(
            console,
            "Service-account automation status",
            purpose="Confirm the headless path is selected and point Kent to the final readiness check.",
            action="Run aeat doctor to verify the active path, API readiness, and any inactive-path drift.",
            source="The service-account key path is already stored in env/.env.",
            browser="No browser flow should be required on this path.",
            success="The service-account key exists and the MCP cache directory exists or was prepared.",
            continuation="uv run aeat doctor",
        )

    if run_doctor:
        from ..doctor import doctor

        doctor()


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

    if json_output or json_output_requested():
        emit_json_success("auth list-providers", render_list_providers_json(rows))
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


async def _close_provider(provider: Any) -> None:
    """Best-effort ``close()`` on an :class:`AuthProvider`-like object.

    Some providers (Cl@ve Móvil) expose an async ``close()``; others
    may grow a synchronous equivalent in the future. The helper
    accepts either by inspecting the return value for a coroutine,
    mirroring the dispatch pattern used inside
    :mod:`aeat.adapters.outbound.aeat.auth._clave_movil` for browser-session teardown.
    """
    close = getattr(provider, "close", None)
    if close is None:
        return
    try:
        result = close()
    except Exception as exc:
        logger.warning("provider close() raised: %s", exc)
        return
    if asyncio.iscoroutine(result):
        try:
            await result
        except Exception as exc:
            logger.warning("provider async close() raised: %s", exc)


async def _do_login(settings: Settings, kind: AuthProviderKind) -> AeatSession:
    """Authenticate and return a frozen :class:`AeatSession` value.

    The `finally` block closes the provider (teardown of the Playwright
    context and browser subprocess) before the session is handed back
    to the caller. This is safe because :class:`AeatSession` is a
    strict frozen Pydantic model with no live resources — every field
    (identity, timestamps, storage-state path, cookie-hash) is a plain
    value already persisted to disk at this point. A future provider
    whose ``AeatSession`` grows a live in-memory handle (e.g. an open
    httpx client) MUST restructure this helper before that lands.
    """
    provider = _registry.build_provider(kind, settings)
    try:
        return await provider.authenticate()
    finally:
        await _close_provider(provider)


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
    from ....adapters.outbound.aeat.auth._clave_movil import (
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

    Uses the same env-writer as ``aeat setup`` (:func:`aeat.core.env_io.write_env_vars`),
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

    from ....core.env_io import write_env_vars

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
    # The CLI never echoes the written values (DNI/NIE + contraste are
    # PII) and no longer surfaces the underlying env-var names either —
    # Kent thinks in human terms ("my NIE", "my support number"), not in
    # UPPER_SNAKE_CASE environment variables. A single prose sentence
    # confirms what the CLI saved and where.
    human_terms: list[str] = []
    if mapping.get("AEAT_CLAVE_MOVIL_DNI_NIE"):
        human_terms.append("your DNI/NIE")
    if mapping.get("AEAT_CLAVE_MOVIL_DNI_FECHA"):
        human_terms.append("the DNI validity date")
    if mapping.get("AEAT_CLAVE_MOVIL_NIE_SOPORTE"):
        human_terms.append("the NIE support number")
    if mapping.get("AEAT_CLAVE_PREFER_NON_QR") == "true":
        human_terms.append("the direct-push preference")
    if mapping.get("AEAT_CLAVE_PREFER_NON_QR") == "false":
        human_terms.append("the QR-code preference")
    if mapping.get("AEAT_AUTH_PROVIDER"):
        human_terms.append("Cl@ve Móvil as the default provider")
    human_list = human_terms[0] if len(human_terms) == 1 else ", ".join(human_terms[:-1]) + ", and " + human_terms[-1]
    _CONSOLE.print(
        f"[green]Saved {human_list} to {env_file}.[/green]\nRun `aeat auth login` to sign in with Cl@ve Móvil."
    )


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
        if json_output or json_output_requested():
            raise CliRefusedBoundaryError(
                f"provider {kind.value} requires an interactive approval step; cannot run with --non-interactive"
            )
        _CONSOLE.print(
            f"[red]provider {kind.value} requires an interactive approval step; cannot run with --non-interactive[/red]"
        )
        raise typer.Exit(code=2)

    try:
        session = asyncio.run(_do_login(settings, kind))
    except _registry.ProviderNotImplementedError as exc:
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]AEAT authentication failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output or json_output_requested():
        # The storage_state_path is intentionally omitted from the JSON
        # surface — it is an internal file location that Kent has no
        # reason to consume from a login command. Downstream scripts
        # that need the path should resolve it via
        # ``aeat.entrypoints.cli.auth._paths.storage_state_paths(settings, kind)``
        # rather than scraping login's output.
        payload = {
            "provider_kind": session.provider_kind.value,
            "identity_nif": session.identity_nif,
            "authenticated_at": session.authenticated_at.isoformat(),
            "idle_deadline": session.idle_deadline.isoformat(),
        }
        emit_json_success("auth login", payload)
        return

    now = datetime.now(UTC)
    remaining_seconds = int((session.idle_deadline - now).total_seconds())
    label = _registry.get_entry(session.provider_kind).label
    if remaining_seconds <= 0:
        _CONSOLE.print(
            f"[yellow]Signed in as {session.identity_nif} via {label}, but the "
            "session is already past its idle deadline. AEAT may refuse subsequent "
            "requests; run `aeat auth login` again if reads fail.[/yellow]"
        )
    else:
        remaining_minutes = max(1, remaining_seconds // 60)
        _CONSOLE.print(
            f"[green]Signed in as {session.identity_nif} via {label}. "
            f"Session expires in about {remaining_minutes}m.[/green]"
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
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if session is None or (kind is not None and session.provider_kind != kind):
        if json_output or json_output_requested():
            emit_json_success("auth status", {"session": None})
        else:
            _CONSOLE.print(render_no_session_line(settings))
        return

    if json_output or json_output_requested():
        emit_json_success("auth status", render_status_json(session))
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
        await _close_provider(provider)


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
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    if persisted is None:
        if json_output or json_output_requested():
            raise CliRefusedBoundaryError(render_no_session_line(settings))
        _CONSOLE.print(render_no_session_line(settings))
        raise typer.Exit(code=1)
    kind = explicit or persisted.provider_kind

    try:
        refreshed, assertion = asyncio.run(_do_whoami(settings, kind))
    except _registry.ProviderNotImplementedError as exc:
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]AEAT probe failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output or json_output_requested():
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
        emit_json_success("auth whoami", payload)
        return

    label = _registry.get_entry(refreshed.provider_kind).label
    if assertion.is_valid:
        _CONSOLE.print(
            f"[green]Signed in as {refreshed.identity_nif} via {label}. AEAT accepted the cached session.[/green]"
        )
    else:
        _CONSOLE.print(
            f"[yellow]The cached {label} session is stale or revoked. Run `aeat auth login` to sign in again.[/yellow]"
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
    if all_providers and provider is not None:
        raise typer.BadParameter(
            "Pass either --provider or --all, not both: --all clears every "
            "provider's cached session, so --provider would be ignored."
        )
    settings = _load_settings()

    removed: list[Path] = []
    cleared_kinds: list[AuthProviderKind] = []

    if all_providers:
        for entry in _registry.iter_entries():
            removed_for_kind = _session.delete(settings, entry.kind)
            if removed_for_kind:
                cleared_kinds.append(entry.kind)
                removed.extend(removed_for_kind)
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
            removed_for_kind = _session.delete(settings, target_kind)
            if removed_for_kind:
                cleared_kinds.append(target_kind)
                removed.extend(removed_for_kind)
    else:
        # No --provider → clear whichever provider currently has a session
        # on disk. This matches Kent's intuition: `aeat auth logout`
        # clears his active session regardless of which provider produced it.
        try:
            persisted = _session.load(settings)
        except _session.CorruptAuthSessionError:
            persisted = None
        if persisted is not None:
            removed_for_kind = _session.delete(settings, persisted.provider_kind)
            if removed_for_kind:
                cleared_kinds.append(persisted.provider_kind)
                removed.extend(removed_for_kind)

    if json_output or json_output_requested():
        emit_json_success(
            "auth logout",
            {
                "cleared_providers": [k.value for k in cleared_kinds],
                "removed_paths": [str(p) for p in removed],
            },
        )
        return

    if not removed:
        _CONSOLE.print("No active session found. Nothing to clear.")
        return

    labels = [_registry.get_entry(k).label for k in cleared_kinds]
    if len(labels) == 1:
        _CONSOLE.print(f"Signed out of {labels[0]}.")
    else:
        joined = ", ".join(labels)
        _CONSOLE.print(f"Signed out of {joined}.")


__all__ = ["app"]
