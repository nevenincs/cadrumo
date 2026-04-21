"""Launch the upstream ``workspace-mcp`` server with repo-local credentials.

This module bridges the tracked, secret-free `.mcp.json` entry to the
gitignored credential sources managed by the AEAT project. It loads
`env/.env` via :mod:`aeat.config`, derives the exact upstream environment
variables `workspace-mcp` expects, forces the refresh-token cache into a
repo-local gitignored directory, and then replaces the current process with the
real server command.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from ..config import PROJECT_ROOT, Settings, load_settings
from ..errors import AeatError

WORKSPACE_MCP_CREDENTIALS_DIR_ENV = "WORKSPACE_MCP_CREDENTIALS_DIR"
WORKSPACE_MCP_SERVICE_ACCOUNT_FILE_ENV = "GOOGLE_SERVICE_ACCOUNT_KEY_FILE"
WORKSPACE_MCP_USER_EMAIL_ENV = "USER_GOOGLE_EMAIL"
WORKSPACE_MCP_COMMAND: tuple[str, ...] = ("uvx", "workspace-mcp", "--tool-tier", "core")
PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR = PROJECT_ROOT / "env" / "workspace-mcp-credentials"


@dataclass(frozen=True)
class LaunchSpec:
    """Immutable launch contract for the upstream ``workspace-mcp`` process."""

    argv: tuple[str, ...]
    env: dict[str, str]
    credentials_dir: Path


def _settings_env_key(field_name: str) -> str:
    """Return the uppercase env-var name for a ``Settings`` field."""

    return field_name.upper()


def _resolve_project_path(raw_path: str) -> Path:
    """Resolve repo-relative credential paths against ``PROJECT_ROOT``."""

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (PROJECT_ROOT / candidate).resolve()


def _format_spec_for_dump(spec: LaunchSpec) -> str:
    """Serialize the launch contract for subprocess-backed boundary tests."""

    redacted_keys = {_settings_env_key("google_oauth_client_secret")}
    relevant_keys = (
        WORKSPACE_MCP_CREDENTIALS_DIR_ENV,
        WORKSPACE_MCP_SERVICE_ACCOUNT_FILE_ENV,
        WORKSPACE_MCP_USER_EMAIL_ENV,
        _settings_env_key("google_application_credentials"),
        _settings_env_key("google_impersonate_email"),
        _settings_env_key("google_oauth_client_id"),
        _settings_env_key("google_oauth_client_secret"),
        _settings_env_key("google_oauth_redirect_uri"),
    )
    payload = {
        "argv": list(spec.argv),
        "credentials_dir": str(spec.credentials_dir),
        "executable": resolve_executable(spec),
        "env": {
            key: ("<redacted>" if key in redacted_keys else spec.env[key]) for key in relevant_keys if key in spec.env
        },
    }
    return json.dumps(payload, sort_keys=True)


def _require_supported_credentials(settings: Settings) -> tuple[bool, Path | None]:
    """Validate the supported auth paths for the upstream MCP server."""

    has_oauth = bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)
    has_partial_oauth = bool(settings.google_oauth_client_id or settings.google_oauth_client_secret)
    service_account_path: Path | None = None

    if settings.google_application_credentials:
        service_account_path = _resolve_project_path(settings.google_application_credentials)

    if has_partial_oauth and not has_oauth and service_account_path is None:
        raise AeatError(
            "google-workspace MCP launch requires either a complete OAuth desktop client "
            "configuration via `aeat oauth-client init` or a configured service-account key path "
            "in `env/.env`."
        )
    if not has_oauth and service_account_path is None:
        raise AeatError(
            "google-workspace MCP launch requires local Google credentials in `env/.env`. "
            "Run `aeat oauth-client init` for the OAuth desktop path or set the service-account key path."
        )
    if service_account_path is not None and not service_account_path.exists():
        if not has_oauth:
            raise AeatError(f"Configured service-account key file does not exist: {service_account_path}")
        service_account_path = None
    return has_oauth, service_account_path


def build_launch_spec(
    settings: Settings,
    *,
    base_env: Mapping[str, str] | None = None,
    extra_args: Sequence[str] = (),
) -> LaunchSpec:
    """Build the upstream argv/env contract from repo-local settings."""

    has_oauth, service_account_path = _require_supported_credentials(settings)
    env = dict(base_env) if base_env is not None else dict(os.environ)

    if has_oauth:
        env[_settings_env_key("google_oauth_client_id")] = settings.google_oauth_client_id
        env[_settings_env_key("google_oauth_client_secret")] = settings.google_oauth_client_secret
        env[_settings_env_key("google_oauth_redirect_uri")] = settings.google_oauth_redirect_uri

    if service_account_path is not None:
        resolved_service_account_path = str(service_account_path)
        env[WORKSPACE_MCP_SERVICE_ACCOUNT_FILE_ENV] = resolved_service_account_path
        env[_settings_env_key("google_application_credentials")] = resolved_service_account_path

    if settings.google_impersonate_email:
        env[_settings_env_key("google_impersonate_email")] = settings.google_impersonate_email
        env[WORKSPACE_MCP_USER_EMAIL_ENV] = settings.google_impersonate_email

    env[WORKSPACE_MCP_CREDENTIALS_DIR_ENV] = str(PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR)
    argv = (*WORKSPACE_MCP_COMMAND, *extra_args)
    return LaunchSpec(argv=argv, env=env, credentials_dir=PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR)


def ensure_credentials_dir(path: Path) -> Path:
    """Create the repo-local credential directory if needed."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_executable(spec: LaunchSpec) -> str:
    """Resolve the process-replacement executable using the launch PATH."""

    executable = shutil.which(spec.argv[0], path=spec.env.get("PATH"))
    if executable is None:
        raise AeatError(f"Required executable not found on PATH: {spec.argv[0]}")
    return executable


def exec_launch_spec(spec: LaunchSpec) -> NoReturn:
    """Replace the current process with the upstream MCP server."""

    executable = resolve_executable(spec)
    argv = [executable, *spec.argv[1:]]
    os.execvpe(executable, argv, spec.env)  # noqa: S606 - fixed project-owned process replacement


def launch_google_workspace(extra_args: Sequence[str] = ()) -> NoReturn:
    """Load settings, derive the upstream launch contract, and exec."""

    settings = load_settings()
    spec = build_launch_spec(settings, extra_args=extra_args)
    ensure_credentials_dir(spec.credentials_dir)
    exec_launch_spec(spec)


def main(argv: Sequence[str] | None = None) -> NoReturn:
    """CLI entry point for ``python -m aeat.mcp.launch_google_workspace``."""

    args = tuple(argv) if argv is not None else tuple(sys.argv[1:])
    if "--dump-launch-spec" in args:
        filtered_args = tuple(arg for arg in args if arg != "--dump-launch-spec")
        settings = load_settings()
        spec = build_launch_spec(settings, extra_args=filtered_args)
        ensure_credentials_dir(spec.credentials_dir)
        sys.stdout.write(f"{_format_spec_for_dump(spec)}\n")
        raise SystemExit(0)
    launch_google_workspace(args)


if __name__ == "__main__":
    main()
