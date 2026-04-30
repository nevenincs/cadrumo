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

from ..auth import GoogleAuthPath, inspect_google_auth
from ..config import PROJECT_ROOT, Settings, load_settings
from ..mcp._errors import McpLaunchError

WORKSPACE_MCP_CREDENTIALS_DIR_ENV = "WORKSPACE_MCP_CREDENTIALS_DIR"
WORKSPACE_MCP_SERVICE_ACCOUNT_FILE_ENV = "GOOGLE_SERVICE_ACCOUNT_KEY_FILE"
WORKSPACE_MCP_USER_EMAIL_ENV = "USER_GOOGLE_EMAIL"
WORKSPACE_MCP_COMMAND: tuple[str, ...] = ("uvx", "workspace-mcp", "--tool-tier", "core")
PROJECT_ENV_EXAMPLE_PATH = PROJECT_ROOT / "env" / ".env.example"
PROJECT_ENV_PATH = PROJECT_ROOT / "env" / ".env"
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


def ensure_project_env_file(
    env_path: Path = PROJECT_ENV_PATH,
    example_path: Path = PROJECT_ENV_EXAMPLE_PATH,
) -> Path:
    """Provision ``env/.env`` from the tracked example when it is missing."""

    if env_path.exists():
        return env_path
    if not example_path.exists():
        raise McpLaunchError(f"Cannot provision env file because the example is missing: {example_path}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example_path, env_path)
    return env_path


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


def _require_supported_credentials(settings: Settings) -> tuple[GoogleAuthPath, Path | None]:
    """Validate the supported auth paths for the upstream MCP server."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if inspection.active_path is None:
        raise McpLaunchError(
            inspection.blocking_reason or "google-workspace MCP launch requires local Google credentials"
        )
    if inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
        if not inspection.desktop_oauth_complete:
            raise McpLaunchError(
                "google-workspace MCP launch requires a complete Desktop OAuth local-dev configuration in env/.env."
            )
        return (inspection.active_path, None)
    service_account_path = inspection.service_account_existing_path
    if service_account_path is None:
        configured = inspection.service_account_configured_path
        if configured is not None:
            raise McpLaunchError(f"Configured service-account key file does not exist: {configured}")
        raise McpLaunchError("google-workspace MCP launch requires a configured service-account key path in env/.env.")
    return (inspection.active_path, _resolve_project_path(str(service_account_path)))


# Keys we propagate from the parent process environment into the
# upstream workspace-mcp child. Everything OUTSIDE this allow-list
# (including AEAT_CERTIFICATE_PASSWORD_SECRET, AEAT_SECRET_PASSPHRASE,
# LLM provider API keys, and any other secret env var the operator has
# set) is intentionally NOT inherited. The upstream MCP server is a
# third-party dependency with its own attack surface; minimise what it
# can read from os.environ. The keys this allow-list permits are the
# bare minimum the upstream actually needs (PATH for executable
# resolution, user-profile / temp-dir keys for credentials cache, and
# the Google-specific keys the build path injects below).
_LAUNCH_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Cross-platform basics — PATH for shutil.which, user-profile
        # vars so the upstream can locate per-user state, locale for
        # output, terminal vars so the child can render correctly.
        "PATH",
        "PATHEXT",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "COLORTERM",
        # POSIX home / temp.
        "HOME",
        "USER",
        "LOGNAME",
        "TMPDIR",
        "TMP",
        # Windows home / temp / shell helpers.
        "USERPROFILE",
        "USERNAME",
        "USERDOMAIN",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "TEMP",
        "COMSPEC",
        # Python interpreter / venv markers (the upstream may import
        # from the same .venv).
        "PYTHONUNBUFFERED",
        "VIRTUAL_ENV",
        "VIRTUAL_ENV_PROMPT",
        # Workspace-MCP-specific keys (set explicitly below; the
        # allow-list also permits any pre-existing operator overrides
        # to flow through).
        WORKSPACE_MCP_CREDENTIALS_DIR_ENV,
        WORKSPACE_MCP_SERVICE_ACCOUNT_FILE_ENV,
        WORKSPACE_MCP_USER_EMAIL_ENV,
    }
)


def _filter_env_to_allowlist(source_env: Mapping[str, str]) -> dict[str, str]:
    """Project ``source_env`` onto the launcher's allow-list.

    Returns a fresh dict containing only allow-listed keys. The
    Google-OAuth / service-account / impersonation keys the launcher
    populates explicitly below are NOT in the allow-list because they
    are pulled from validated settings, not from the parent process
    env (the operator's pre-existing values would be ambiguous).
    Settings-derived keys are added on top of the allow-list copy.
    """
    return {key: value for key, value in source_env.items() if key in _LAUNCH_ENV_ALLOWLIST}


def build_launch_spec(
    settings: Settings,
    *,
    base_env: Mapping[str, str] | None = None,
    extra_args: Sequence[str] = (),
) -> LaunchSpec:
    """Build the upstream argv/env contract from repo-local settings."""

    active_path, service_account_path = _require_supported_credentials(settings)
    # Project the parent environment onto the explicit allow-list so
    # secrets (certificate passphrase, master-key passphrase, LLM API
    # keys) never flow into the spawned workspace-mcp server. The
    # settings-derived Google keys are injected below from validated
    # config, not from os.environ.
    raw_env = base_env if base_env is not None else os.environ
    env = _filter_env_to_allowlist(raw_env)

    if active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
        env[_settings_env_key("google_oauth_client_id")] = settings.google_oauth_client_id
        env[_settings_env_key("google_oauth_client_secret")] = settings.google_oauth_client_secret
        env[_settings_env_key("google_oauth_redirect_uri")] = settings.google_oauth_redirect_uri

    if active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION and service_account_path is not None:
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
        raise McpLaunchError(f"Required executable not found on PATH: {spec.argv[0]}")
    return executable


def exec_launch_spec(spec: LaunchSpec) -> NoReturn:
    """Replace the current process with the upstream MCP server."""

    executable = resolve_executable(spec)
    argv = [executable, *spec.argv[1:]]
    os.execvpe(executable, argv, spec.env)  # noqa: S606 - fixed project-owned process replacement


def launch_google_workspace(extra_args: Sequence[str] = ()) -> NoReturn:
    """Load settings, derive the upstream launch contract, and exec."""

    ensure_project_env_file()
    settings = load_settings()
    spec = build_launch_spec(settings, extra_args=extra_args)
    ensure_credentials_dir(spec.credentials_dir)
    exec_launch_spec(spec)


def main(argv: Sequence[str] | None = None) -> NoReturn:
    """CLI entry point for ``python -m aeat.mcp.launch_google_workspace``."""

    args = tuple(argv) if argv is not None else tuple(sys.argv[1:])
    if "--dump-launch-spec" in args:
        filtered_args = tuple(arg for arg in args if arg != "--dump-launch-spec")
        ensure_project_env_file()
        settings = load_settings()
        spec = build_launch_spec(settings, extra_args=filtered_args)
        ensure_credentials_dir(spec.credentials_dir)
        sys.stdout.write(f"{_format_spec_for_dump(spec)}\n")
        raise SystemExit(0)
    launch_google_workspace(args)


if __name__ == "__main__":
    main()
