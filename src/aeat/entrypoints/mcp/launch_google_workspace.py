"""Launch the upstream ``workspace-mcp`` server with repo-local credentials.

Bridges the tracked, secret-free ``.mcp.json`` entry to the gitignored
credential sources managed by the AEAT project. The launcher loads
``env/.env`` via :mod:`aeat.core.config`, validates the active
:class:`aeat.adapters.outbound.google.GoogleAuthPath` via
:func:`aeat.adapters.outbound.google.inspect_google_auth`, derives the
exact upstream environment variables ``workspace-mcp`` expects, forces
the refresh-token cache into a repo-local gitignored directory, and then
replaces the current process with the real server command.

The parent-process environment is projected onto an explicit allow-list
so secrets such as the certificate passphrase, master-key passphrase, and
LLM provider API keys never flow into the spawned ``workspace-mcp``
server.
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

from ...adapters.outbound.google import GoogleAuthPath, inspect_google_auth
from ...core.config import PROJECT_ROOT, Settings, load_settings
from ._errors import McpLaunchError

WORKSPACE_MCP_CREDENTIALS_DIR_ENV = "WORKSPACE_MCP_CREDENTIALS_DIR"
WORKSPACE_MCP_SERVICE_ACCOUNT_FILE_ENV = "GOOGLE_SERVICE_ACCOUNT_KEY_FILE"
WORKSPACE_MCP_USER_EMAIL_ENV = "USER_GOOGLE_EMAIL"
WORKSPACE_MCP_COMMAND: tuple[str, ...] = ("uvx", "workspace-mcp", "--tool-tier", "core")
PROJECT_ENV_EXAMPLE_PATH = PROJECT_ROOT / "env" / ".env.example"
PROJECT_ENV_PATH = PROJECT_ROOT / "env" / ".env"
PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR = PROJECT_ROOT / "env" / "workspace-mcp-credentials"


@dataclass(frozen=True)
class LaunchSpec:
    """Immutable launch contract for the upstream ``workspace-mcp`` process.

    Attributes:
        argv: Argv tuple to exec, leading with the executable name.
        env: Environment mapping the child process inherits.
        credentials_dir: Repo-local directory the upstream MCP server uses
            for its OAuth refresh-token cache.
    """

    argv: tuple[str, ...]
    env: dict[str, str]
    credentials_dir: Path


def _settings_env_key(field_name: str) -> str:
    """Return the uppercase environment-variable name for a
    :class:`aeat.core.config.Settings` field.
    """

    return field_name.upper()


def _resolve_project_path(raw_path: str) -> Path:
    """Resolve repo-relative credential paths against
    :data:`aeat.core.config.PROJECT_ROOT`.

    Args:
        raw_path: A user-supplied path; may be absolute, contain ``~``, or
            be relative to the project root.

    Returns:
        The resolved absolute :class:`pathlib.Path`.
    """

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (PROJECT_ROOT / candidate).resolve()


def ensure_project_env_file(
    env_path: Path = PROJECT_ENV_PATH,
    example_path: Path = PROJECT_ENV_EXAMPLE_PATH,
) -> Path:
    """Provision ``env/.env`` from the tracked example when it is missing.

    Args:
        env_path: Destination path for the project env file.
        example_path: Tracked template to copy from.

    Returns:
        The path to the (now-present) env file.

    Raises:
        :exc:`aeat.core.errors.McpLaunchError`: When ``example_path`` does
            not exist.
    """

    if env_path.exists():
        return env_path
    if not example_path.exists():
        raise McpLaunchError(f"Cannot provision env file because the example is missing: {example_path}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example_path, env_path)
    return env_path


def _format_spec_for_dump(spec: LaunchSpec) -> str:
    """Serialize the launch contract for subprocess-backed boundary tests.

    Renders argv, the resolved executable, the credentials directory, and
    the relevant environment keys as deterministic JSON. The OAuth client
    secret is replaced with ``"<redacted>"`` so the dump can flow through
    test logs without leaking secrets.
    """

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
    """Validate the supported auth paths for the upstream MCP server.

    Inspects the project state via
    :func:`aeat.adapters.outbound.google.inspect_google_auth` and either
    returns the active :class:`aeat.adapters.outbound.google.GoogleAuthPath`
    paired with the resolved service-account key path (or ``None`` for the
    Desktop OAuth path), or raises with a precise blocking reason.

    Raises:
        :exc:`aeat.core.errors.McpLaunchError`: When no supported auth path
            is configured, the Desktop OAuth configuration is incomplete,
            or the configured service-account key file is missing.
    """

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
    """Project ``source_env`` onto :data:`_LAUNCH_ENV_ALLOWLIST`.

    Returns a fresh dict containing only allow-listed keys. The
    workspace-MCP-specific keys (:data:`WORKSPACE_MCP_CREDENTIALS_DIR_ENV`,
    :data:`WORKSPACE_MCP_SERVICE_ACCOUNT_FILE_ENV`, and
    :data:`WORKSPACE_MCP_USER_EMAIL_ENV`) are in the allow-list so any
    operator-set values flow through; :func:`build_launch_spec` then
    overwrites the credentials-dir, service-account, and impersonation
    keys with values pulled from validated settings, so the final child
    env is settings-correct regardless of what the operator had in their
    parent env.

    The Google OAuth client id, secret, and redirect URI keys are NOT in
    the allow-list — those flow only from validated settings via the
    explicit injection in :func:`build_launch_spec`, because operator
    pre-existing values for those keys would be ambiguous.

    Args:
        source_env: Parent process environment to filter.

    Returns:
        A new dict containing only the allow-listed keys.
    """
    return {key: value for key, value in source_env.items() if key in _LAUNCH_ENV_ALLOWLIST}


def build_launch_spec(
    settings: Settings,
    *,
    base_env: Mapping[str, str] | None = None,
    extra_args: Sequence[str] = (),
) -> LaunchSpec:
    """Build the upstream argv and env contract from repo-local settings.

    Args:
        settings: Validated :class:`aeat.core.config.Settings`.
        base_env: Optional explicit parent environment to project. Defaults
            to :data:`os.environ`.
        extra_args: Extra positional arguments appended after
            :data:`WORKSPACE_MCP_COMMAND`.

    Returns:
        A populated :class:`LaunchSpec`.

    Raises:
        :exc:`aeat.core.errors.McpLaunchError`: When credential validation
            via :func:`_require_supported_credentials` fails.
    """

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
    """Create the repo-local credential directory if it does not exist.

    Args:
        path: Target credentials directory.

    Returns:
        The (now-existing) directory path.
    """

    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_executable(spec: LaunchSpec) -> str:
    """Resolve the process-replacement executable using the launch ``PATH``.

    Args:
        spec: The :class:`LaunchSpec` whose ``argv[0]`` and ``env["PATH"]``
            are consulted.

    Returns:
        Absolute path to the resolved executable.

    Raises:
        :exc:`aeat.core.errors.McpLaunchError`: When the executable cannot
            be found on the launch ``PATH``.
    """

    executable = shutil.which(spec.argv[0], path=spec.env.get("PATH"))
    if executable is None:
        raise McpLaunchError(f"Required executable not found on PATH: {spec.argv[0]}")
    return executable


def exec_launch_spec(spec: LaunchSpec) -> NoReturn:
    """Replace the current process with the upstream MCP server.

    Calls :func:`os.execvpe` and therefore never returns on success.

    Args:
        spec: Validated :class:`LaunchSpec` to exec.
    """

    executable = resolve_executable(spec)
    argv = [executable, *spec.argv[1:]]
    os.execvpe(executable, argv, spec.env)  # noqa: S606 - fixed project-owned process replacement


def launch_google_workspace(extra_args: Sequence[str] = ()) -> NoReturn:
    """Load settings, derive the upstream launch contract, and exec.

    Provisions ``env/.env`` from the example if needed, loads
    :class:`aeat.core.config.Settings`, builds the :class:`LaunchSpec`,
    ensures the credentials cache directory exists, and replaces the
    current process via :func:`exec_launch_spec`.

    Args:
        extra_args: Extra positional arguments forwarded to
            :func:`build_launch_spec`.
    """

    ensure_project_env_file()
    settings = load_settings()
    spec = build_launch_spec(settings, extra_args=extra_args)
    ensure_credentials_dir(spec.credentials_dir)
    exec_launch_spec(spec)


def main(argv: Sequence[str] | None = None) -> NoReturn:
    """CLI entry point for ``python -m aeat.entrypoints.mcp.launch_google_workspace``.

    Recognises a single special flag, ``--dump-launch-spec``: when present,
    the resolved :class:`LaunchSpec` is serialised to stdout via
    :func:`_format_spec_for_dump` and the process exits ``0`` without
    invoking the upstream MCP server. All other arguments are forwarded
    verbatim to :func:`launch_google_workspace`.

    Args:
        argv: Optional argv override; defaults to ``sys.argv[1:]``.
    """

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
