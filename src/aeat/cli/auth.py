"""Kent-facing Google authentication entrypoint."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer
from pydantic_settings import SettingsConfigDict
from rich.console import Console

from ..auth import SCOPES, GoogleAuthPath, get_credentials, inspect_google_auth
from ..config import PROJECT_ROOT, Settings
from ..env_io import write_env_vars
from ..mcp.launch_google_workspace import (
    ensure_credentials_dir,
    ensure_project_env_file,
)
from .oauth import CREDENTIALS_PAGE_TEMPLATE, REQUIRED_BLOCK, parse_oauth_client_json

app = typer.Typer(
    name="auth",
    no_args_is_help=True,
    help="Kent-first Google authentication flow for Desktop OAuth local-dev or Service-account automation.",
)


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


def _persist_selected_path(path: GoogleAuthPath) -> None:
    write_env_vars(PROJECT_ROOT / "env" / ".env", {"GOOGLE_AUTH_PATH": path.value})


def _select_path(settings: Settings, requested_path: GoogleAuthPath | None) -> GoogleAuthPath:
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if requested_path is not None:
        return requested_path
    if inspection.active_path is not None:
        return inspection.active_path
    return GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV


def _mcp_credentials_dir() -> Path:
    return PROJECT_ROOT / "env" / "workspace-mcp-credentials"


def _settings() -> Settings:
    class ProjectRootSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=PROJECT_ROOT / "env" / ".env",
            env_file_encoding="utf-8",
            env_ignore_empty=True,
        )

    return ProjectRootSettings(aeat_token_dir=PROJECT_ROOT / ".tokens")


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
    selected_path = _select_path(_settings(), path)

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

        inspection = inspect_google_auth(_settings(), project_root=PROJECT_ROOT)
        if reset_cli_token and inspection.oauth_token_exists:
            inspection.oauth_token_path.unlink(missing_ok=True)
            inspection = inspect_google_auth(_settings(), project_root=PROJECT_ROOT)
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
            project = _settings().google_cloud_project or "<your-project-id>"
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
                continuation=("uv run aeat auth init --path desktop-oauth-local-dev --json <downloaded-json>"),
            )
            raise typer.Exit(code=1)

        _persist_selected_path(selected_path)
        inspection = inspect_google_auth(_settings(), project_root=PROJECT_ROOT)

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
            _ = get_credentials(_settings(), scopes=SCOPES)
            inspection = inspect_google_auth(_settings(), project_root=PROJECT_ROOT)

        if prepare_mcp and not inspection.mcp_credentials_dir_exists:
            ensure_credentials_dir(_mcp_credentials_dir())
            inspection = inspect_google_auth(_settings(), project_root=PROJECT_ROOT)
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

        next_command = "uv run aeat doctor"
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
            continuation=next_command,
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

        inspection = inspect_google_auth(_settings(), project_root=PROJECT_ROOT)
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

        _persist_selected_path(selected_path)
        inspection = inspect_google_auth(_settings(), project_root=PROJECT_ROOT)

        if prepare_mcp and not inspection.mcp_credentials_dir_exists:
            ensure_credentials_dir(_mcp_credentials_dir())
            inspection = inspect_google_auth(_settings(), project_root=PROJECT_ROOT)

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
        from .doctor import doctor

        doctor()
