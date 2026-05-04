"""``aeat auth`` sub-app — authentication provider management.

The operator runs these commands to discover which providers are
configured, sign in, inspect the live session TTL, and clear a
persisted session. The four subcommands are thin dispatch layers over
the shared ``AuthProvider`` abstraction in
:mod:`aeat.adapters.outbound.aeat.auth`; the CLI owns argument parsing,
rendering, and process exit mapping only.
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

from ....adapters.outbound.google import (
    SCOPES,
    GoogleAuthPath,
    get_credentials,
    inspect_google_auth,
)
from ....application.auth import AuthProviderKind
from ....core.config import PROJECT_ROOT, Settings
from ....core.env_io import write_env_vars
from ....core.logging import get_logger
from .._errors import CliRefusedBoundaryError, json_output_requested
from .._i18n import tr
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
        "Operator-facing auth setup plus AEAT authentication provider management: "
        "init, configure, list-providers, login, status, whoami, logout."
    ),
)

_CONSOLE = Console()


def ensure_credentials_dir(path: Path) -> Path:
    """Create and return the Google credentials directory."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_project_env_file(env_path: Path, example_path: Path) -> Path:
    """Ensure the project env file exists, seeding from the example when present."""

    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        if example_path.exists():
            shutil.copyfile(example_path, env_path)
        else:
            env_path.touch()
    return env_path


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
    purpose_label = tr("auth.init.t_954326")
    action_label = tr("auth.init.t_714790")
    source_label = tr("auth.init.t_322689")
    browser_label = tr("auth.init.t_853374")
    success_label = tr("auth.init.t_105867")
    next_label = tr("auth.init.t_351011")
    console.print(f"[bold]{title}[/bold]")
    console.print(f"{purpose_label} {purpose}")
    console.print(f"{action_label} {action}")
    console.print(f"{source_label} {source}")
    console.print(f"{browser_label} {browser}")
    console.print(f"{success_label} {success}")
    console.print(f"{next_label} {continuation}")
    console.print()


def _copy_oauth_client_json(json_path: Path) -> Path:
    raw = json_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("_copy_oauth_client_json: invalid JSON in %s", json_path, exc_info=True)
        raise ValueError(f"invalid JSON in {json_path}: {exc}") from exc
    client_id, client_secret = parse_oauth_client_json(payload)
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
        """Settings shape pinned to the repository's ``env/.env`` file."""

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
        kind = AuthProviderKind(raw)
    except ValueError as exc:
        ", ".join(k.value for k in _registry.iter_kinds())
        raise typer.BadParameter(tr("auth.init.t_686896")) from exc
    if kind not in _registry.iter_kinds():
        ", ".join(k.value for k in _registry.iter_kinds())
        raise typer.BadParameter(tr("auth.init.t_151679"))
    return kind


@app.command("init", help="Guide the operator through the supported Google authentication paths.")
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
                console.print("[red]" + tr("auth.init.t_263360") + "[/]")
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
                continuation=("Launch the Google Workspace MCP server once to finish MCP credential preparation."),
            )

        _print_step(
            console,
            "Desktop OAuth local-dev status",
            purpose=(
                "Confirm which remaining step is on the path from local auth to verified CLI/bootstrap readiness."
            ),
            action=(
                "If you need MCP access, launch the Google Workspace MCP server once. "
                "Then verify the current state with aeat doctor."
            ),
            source="This decision depends on whether your workflow needs MCP credential preparation.",
            browser="Launching the MCP server may open a browser-managed OAuth flow. aeat doctor does not.",
            success=(
                "Desktop OAuth client material is present, the CLI token is usable, "
                "and the MCP cache directory is prepared for first launch."
            ),
            continuation="uv run aeat doctor",
        )
    else:
        if service_account_json is not None:
            if not service_account_json.exists():
                console.print("[red]" + tr("auth.init.t_352935") + "[/]")
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
            purpose="Confirm the headless path is selected and point the operator to the final readiness check.",
            action="Run aeat doctor to verify the active path, API readiness, and any inactive-path drift.",
            source="The service-account key path is already stored in env/.env.",
            browser="No browser flow should be required on this path.",
            success="The service-account key exists and the MCP cache directory exists or was prepared.",
            continuation="uv run aeat doctor",
        )

    if run_doctor:
        from ..doctor import doctor

        doctor()


@app.command("list-providers", help="List supported AEAT auth providers and their current state.")
def list_providers(
    configured_only: bool = typer.Option(
        False,
        "--configured",
        help="Filter to providers that are fully configured and available.",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        help="Include hidden provider entries when the registry defines any.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON instead of a pretty table.",
    ),
) -> None:
    """Operator-facing overview of every supported auth provider in the registry."""
    del show_all  # The registry has no hidden entries to add.
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
    except (_registry.NoConfiguredProviderError, _registry.UnknownProviderError) as exc:
        raise typer.BadParameter(str(exc)) from exc


async def _close_provider(provider: Any) -> None:
    """Best-effort ``close()`` on an :class:`AuthProvider`-like object.

    Some providers (Cl@ve Móvil) expose an async ``close()``; others
    expose a synchronous one. The helper accepts either by inspecting
    the return value for a coroutine, mirroring the dispatch pattern used inside
    :mod:`aeat.adapters.outbound.aeat.auth._clave_movil` for browser-session teardown.
    """
    close = getattr(provider, "close", None)
    if close is None:
        return
    try:
        result = close()
    except Exception:  # auth provider close() exception surface varies by provider; teardown must not abort
        logger.warning("provider close raised", exc_info=True)
        return
    if asyncio.iscoroutine(result):
        try:
            await result
        except Exception:  # async auth provider close() exception surface varies by provider; teardown must not abort
            logger.warning("provider async close raised", exc_info=True)


async def _do_login(settings: Settings, kind: AuthProviderKind) -> AeatSession:
    """Authenticate and return a frozen :class:`AeatSession` value.

    The `finally` block closes the provider (teardown of the Playwright
    context and browser subprocess) before the session is handed back
    to the caller. This is safe because :class:`AeatSession` is a
    strict frozen Pydantic model with no live resources — every field
    (identity, timestamps, storage-state path, cookie-hash) is a plain
    value already persisted to disk at this point.
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
        raise typer.BadParameter(tr("auth.init.t_178097"))
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
    logger.warning(
        "_resolve_env_file: Settings.env_file has unsupported shape %s; cannot determine env file path",
        type(env_file).__name__,
    )
    raise typer.BadParameter(tr("auth.init.t_589739"))


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
        help="Provider to configure.",
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
        raise typer.BadParameter(tr("auth.init.t_549784"))

    settings = _load_settings()
    env_file = _resolve_env_file(settings)

    if dni_nie is None and not non_interactive:
        _CONSOLE.print(tr("auth.init.t_201308"))

    if dni_nie is None:
        if non_interactive:
            raise typer.BadParameter(tr("auth.init.t_833547"))
        dni_nie = typer.prompt(tr("auth.init.t_834743")).strip().upper()
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
                raise typer.BadParameter(tr("auth.init.t_386762"))
            dni_fecha = typer.prompt(tr("auth.init.t_958045")).strip()
        if identity_kind == "NIE" and not nie_soporte:
            if non_interactive:
                raise typer.BadParameter(tr("auth.init.t_479907"))
            nie_soporte = typer.prompt(tr("auth.init.t_944378")).strip()

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
    logger.info("configure: wrote %d key(s) for provider %s", len(mapping), kind.value)
    # The CLI never echoes the written values (DNI/NIE + contraste are
    # PII) and no longer surfaces the underlying env-var names either —
    # the operator thinks in human terms ("my NIE", "my support number"),
    # not in UPPER_SNAKE_CASE environment variables. A single prose
    # sentence confirms what the CLI saved and where.
    human_terms: list[str] = []
    if mapping.get("AEAT_CLAVE_MOVIL_DNI_NIE"):
        human_terms.append(tr("auth.init.t_994186"))
    if mapping.get("AEAT_CLAVE_MOVIL_DNI_FECHA"):
        human_terms.append(tr("auth.init.t_316510"))
    if mapping.get("AEAT_CLAVE_MOVIL_NIE_SOPORTE"):
        human_terms.append(tr("auth.init.t_770369"))
    if mapping.get("AEAT_CLAVE_PREFER_NON_QR") == "true":
        human_terms.append(tr("auth.init.t_912253"))
    if mapping.get("AEAT_CLAVE_PREFER_NON_QR") == "false":
        human_terms.append(tr("auth.init.t_725014"))
    if mapping.get("AEAT_AUTH_PROVIDER"):
        human_terms.append(tr("auth.init.t_542731"))
    if len(human_terms) == 1:
        human_terms[0]
    else:
        and_word = tr("auth.init.t_497666")
        ", ".join(human_terms[:-1]) + and_word + human_terms[-1]
    _CONSOLE.print("[green]" + tr("auth.init.t_637763") + "[/green]\n" + tr("auth.init.t_370466"))


@app.command("login", help="Authenticate with the selected provider and cache the session.")
def login(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Auth provider kind (certificate, clave_movil).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Refuse to run providers that need a human in the loop (Cl@ve Móvil).",
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
        msg = tr("auth.init.t_273946")
        if json_output or json_output_requested():
            raise CliRefusedBoundaryError(msg)
        _CONSOLE.print(f"[red]{msg}[/red]")
        raise typer.Exit(code=2)

    try:
        session = asyncio.run(_do_login(settings, kind))
    except _registry.ProviderUnavailableError as exc:
        logger.error("login: provider unavailable: %s", kind.value, exc_info=True)
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        logger.error("login: authentication failed for provider %s", kind.value, exc_info=True)
        if json_output or json_output_requested():
            raise
        _CONSOLE.print("[red]" + tr("auth.init.t_938392") + "[/red]")
        raise typer.Exit(code=1) from exc

    logger.info("login: authenticated via %s", kind.value)
    if json_output or json_output_requested():
        # The storage_state_path is intentionally omitted from the JSON
        # surface — it is an internal file location that the operator has
        # no reason to consume from a login command. Downstream scripts
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
    if remaining_seconds <= 0:
        _CONSOLE.print("[yellow]" + tr("auth.init.t_092134") + "[/yellow]")
    else:
        max(1, remaining_seconds // 60)
        _CONSOLE.print("[green]" + tr("auth.init.t_941077") + "[/green]")


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
        logger.debug("status: no active session (kind=%s)", kind.value if kind is not None else "any")
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

    Uses ``probe_persisted_session()`` on providers that expose one.
    Falls back to the generic
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
    except _registry.ProviderUnavailableError as exc:
        logger.error("whoami: provider unavailable: %s", kind.value, exc_info=True)
        if json_output or json_output_requested():
            raise
        _CONSOLE.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        logger.error("whoami: probe failed for provider %s", kind.value, exc_info=True)
        if json_output or json_output_requested():
            raise
        _CONSOLE.print("[red]" + tr("auth.init.t_908949") + "[/red]")
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

    if assertion.is_valid:
        _CONSOLE.print("[green]" + tr("auth.init.t_888711") + "[/green]")
    else:
        _CONSOLE.print("[yellow]" + tr("auth.init.t_906241") + "[/yellow]")
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
        raise typer.BadParameter(tr("auth.init.t_950022"))
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
            logger.warning(
                "logout: corrupt session for provider %s; proceeding to delete",
                target_kind.value,
                exc_info=True,
            )
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
        # No --provider clears whichever provider has a session on disk.
        # This matches the operator's intuition: `aeat auth logout` clears
        # the active session regardless of which provider produced it.
        try:
            persisted = _session.load(settings)
        except _session.CorruptAuthSessionError:
            logger.warning("logout: corrupt session on disk; cannot determine provider; skipping delete", exc_info=True)
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
        _CONSOLE.print(tr("auth.init.t_594919"))
        return

    labels = [_registry.get_entry(k).label for k in cleared_kinds]
    if len(labels) == 1:
        _CONSOLE.print(tr("auth.init.t_186277"))
    else:
        ", ".join(labels)
        _CONSOLE.print(tr("auth.init.t_979591"))


__all__ = ["app"]
