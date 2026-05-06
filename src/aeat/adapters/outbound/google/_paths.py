"""Google-auth path inspection and deterministic selection.

Resolves the operator's chosen Google authentication path (Desktop OAuth
local-dev vs. Service-account automation), inspects the local material that
backs each path, and reports whether the CLI and MCP transports are ready
to use. Used by :mod:`aeat.adapters.outbound.google` and the operator-facing
``aeat google ...`` commands to surface a single deterministic "active path"
without ever triggering a browser flow.

The two supported paths are encoded in :class:`GoogleAuthPath` and the full
inspection result lives in :class:`GoogleAuthInspection`.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from ....core.classification import SensitivityClass
from ...persistence.storage.sql import SecureObjectRepository

if TYPE_CHECKING:
    from ....core.config import Settings


class GoogleAuthPath(StrEnum):
    """Named operator-facing Google auth paths supported by the repo.

    Attributes:
        DESKTOP_OAUTH_LOCAL_DEV: Interactive Desktop OAuth client flow
            intended for local developer use; backed by
            ``GOOGLE_OAUTH_CLIENT_ID`` and ``GOOGLE_OAUTH_CLIENT_SECRET``
            and a repo-local refresh-token cache.
        SERVICE_ACCOUNT_AUTOMATION: Non-interactive service-account flow
            intended for unattended automation; backed by
            ``GOOGLE_APPLICATION_CREDENTIALS`` pointing at a JSON key file.
    """

    DESKTOP_OAUTH_LOCAL_DEV = "desktop-oauth-local-dev"
    SERVICE_ACCOUNT_AUTOMATION = "service-account-automation"


DESKTOP_OAUTH_REQUIRED_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
)
"""OAuth scopes the Desktop OAuth local-dev token cache must carry to be usable."""

_OAUTH_TOKEN_NAMESPACE = "aeat.outbound.google.oauth_tokens"  # noqa: S105 - secure-object namespace, not a token
_OAUTH_TOKEN_VERSION = 1
_OAUTH_CLIENT_NAMESPACE = "aeat.outbound.google.oauth_clients"
_OAUTH_CLIENT_VERSION = 1
_SERVICE_ACCOUNT_NAMESPACE = "aeat.outbound.google.service_accounts"
_SERVICE_ACCOUNT_VERSION = 1


def adc_well_known_path() -> Path:
    """Return the well-known path where gcloud writes ADC JSON.

    Honours the ``CLOUDSDK_CONFIG`` env var override; otherwise resolves to
    ``%APPDATA%/gcloud/application_default_credentials.json`` on Windows and
    ``~/.config/gcloud/application_default_credentials.json`` on POSIX.

    Returns:
        Filesystem path that gcloud's ``application-default login`` writes to.
    """

    override = os.environ.get("CLOUDSDK_CONFIG")
    if override:
        return Path(override) / "application_default_credentials.json"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def normalize_google_auth_path(raw_path: object) -> GoogleAuthPath | None:
    """Normalize a config value into a supported Google auth path.

    Accepts an existing :class:`GoogleAuthPath` member, a string matching one
    of the enum values (case-insensitive, surrounding whitespace tolerated),
    or any other value; returns ``None`` when the input cannot be resolved.

    Args:
        raw_path: Untrusted config value sourced from settings or env vars.

    Returns:
        The matching :class:`GoogleAuthPath` member, or ``None`` when the
        value is missing, blank, or unrecognised.
    """

    if isinstance(raw_path, GoogleAuthPath):
        return raw_path
    if not isinstance(raw_path, str):
        return None
    stripped = raw_path.strip().lower()
    if not stripped:
        return None
    for path in GoogleAuthPath:
        if stripped == path.value:
            return path
    return None


def resolve_project_relative_path(raw_path: str) -> Path:
    """Resolve a potentially repo-relative path against the current cwd.

    Args:
        raw_path: Raw filesystem path string; ``~`` is expanded.

    Returns:
        Absolute :class:`pathlib.Path` — the input unchanged if already
        absolute, or resolved against the current working directory.
    """

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return candidate.resolve()


@dataclass(frozen=True)
class GoogleAuthInspection:
    """Resolved Google-auth path plus the local material that backs it.

    Frozen snapshot returned by :func:`inspect_google_auth`. Carries the
    operator-configured path, the deterministically-resolved active path,
    and every input the resolver consulted; downstream consumers inspect
    specific attributes to render diagnostics or gate command execution.

    Attributes:
        configured_path: The :class:`GoogleAuthPath` declared via
            ``GOOGLE_AUTH_PATH``, or ``None`` when nothing was configured.
        active_path: The path the resolver actually selected. ``None`` when
            no path can be activated (see :attr:`blocking_reason`).
        desktop_oauth_complete: ``True`` when both the OAuth client id and
            secret are configured.
        desktop_oauth_partial: ``True`` when at least one Desktop OAuth
            client field is set but the pair is incomplete.
        desktop_oauth_json_path: Path to the optional Desktop OAuth client
            JSON file when configured.
        service_account_configured_path: Path declared via
            ``GOOGLE_APPLICATION_CREDENTIALS``.
        service_account_existing_path: The configured service-account path
            when the file actually exists on disk; otherwise ``None``.
        oauth_token_path: Repo-local Desktop OAuth refresh-token cache path.
        mcp_credentials_dir: Workspace MCP credentials directory.
        adc_path: Well-known gcloud ADC path; see :func:`adc_well_known_path`.
        oauth_token_issue: Human-readable issue describing why the cached
            OAuth token cannot be used; ``None`` when usable.
        blocking_reason: Human-readable reason why no path could be
            activated; ``None`` when :attr:`active_path` is set.
    """

    configured_path: GoogleAuthPath | None
    active_path: GoogleAuthPath | None
    desktop_oauth_complete: bool
    desktop_oauth_partial: bool
    desktop_oauth_json_path: Path | None
    service_account_configured_path: Path | None
    service_account_existing_path: Path | None
    oauth_token_path: Path
    mcp_credentials_dir: Path
    adc_path: Path
    oauth_token_issue: str | None
    blocking_reason: str | None

    @property
    def is_ambiguous(self) -> bool:
        """Whether both auth families are configured without an explicit pick."""
        return self.active_path is None and self.blocking_reason is not None and "Both" in self.blocking_reason

    @property
    def oauth_token_exists(self) -> bool:
        """Whether the repo-local OAuth refresh-token cache exists."""
        return oauth_token_cache_exists(self.oauth_token_path)

    @property
    def mcp_credentials_exist(self) -> bool:
        """Whether the MCP credentials directory exists and contains material."""
        return self.mcp_credentials_dir.exists() and any(self.mcp_credentials_dir.iterdir())

    @property
    def mcp_credentials_dir_exists(self) -> bool:
        """Whether the MCP credentials directory itself exists, even if empty."""
        return self.mcp_credentials_dir.exists()

    @property
    def adc_exists(self) -> bool:
        """Whether gcloud's well-known ADC file exists on disk."""
        return self.adc_path.exists()

    @property
    def inactive_path_drift(self) -> str | None:
        """Human-readable note when the inactive path is partially configured.

        Returns a short label describing which inactive-path config was
        ignored (so operators can clean it up), or ``None`` when the
        inactive path leaves no detectable trace.
        """
        if self.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV and self.service_account_configured_path:
            if self.service_account_existing_path is None:
                return f"ignored stale service-account path: {self.service_account_configured_path}"
            return f"ignored service-account automation config: {self.service_account_existing_path}"
        if self.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION and self.desktop_oauth_complete:
            return "ignored Desktop OAuth local-dev config"
        if self.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION and self.desktop_oauth_partial:
            return "ignored partial Desktop OAuth client config"
        return None

    @property
    def cli_ready(self) -> bool:
        """Whether the active path can serve CLI requests without further setup."""
        if self.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
            return self.desktop_oauth_complete and self.oauth_token_issue is None
        if self.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION:
            return self.service_account_existing_path is not None
        return False

    @property
    def mcp_ready(self) -> bool:
        """Whether the active path can serve MCP requests with current credentials."""
        if self.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
            return self.desktop_oauth_complete and self.mcp_credentials_exist
        if self.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION:
            return self.service_account_existing_path is not None and self.mcp_credentials_exist
        return False


def inspect_oauth_token_cache(token_path: Path) -> str | None:
    """Return ``None`` when the Desktop OAuth token cache looks usable.

    Inspects the JSON shape, refresh-token presence, and granted scopes
    against :data:`DESKTOP_OAUTH_REQUIRED_SCOPES`; never performs network
    I/O and never attempts a refresh.

    Args:
        token_path: Path to the repo-local Desktop OAuth token JSON file.

    Returns:
        A human-readable issue string when the cache is unusable
        (missing, malformed, or missing required scopes), or ``None``
        when the cache is well-formed.
    """

    payload = load_oauth_token_cache(token_path)
    if payload is None:
        return "repo-local CLI OAuth token missing"
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        return f"repo-local CLI OAuth token is unreadable: {exc.__class__.__name__}"
    if not isinstance(parsed, dict):
        return "repo-local CLI OAuth token is malformed"
    refresh_token = parsed.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        return "repo-local CLI OAuth token is missing a refresh_token"
    raw_scopes = parsed.get("scopes")
    if not isinstance(raw_scopes, list):
        return "repo-local CLI OAuth token is missing its scope list"
    granted = {str(scope) for scope in raw_scopes}
    missing = sorted(set(DESKTOP_OAUTH_REQUIRED_SCOPES) - granted)
    if missing:
        missing_csv = ", ".join(missing)
        return f"repo-local CLI OAuth token is missing required scopes: {missing_csv}"
    return None


def oauth_token_cache_exists(token_path: Path) -> bool:
    """Return whether an encrypted OAuth token cache exists for ``token_path``."""

    return SecureObjectRepository().exists(_OAUTH_TOKEN_NAMESPACE, _oauth_token_key(token_path))


def load_oauth_token_cache(token_path: Path) -> str | None:
    """Load the encrypted OAuth token cache payload."""

    record = SecureObjectRepository().load(
        _OAUTH_TOKEN_NAMESPACE,
        _oauth_token_key(token_path),
        expected_class=SensitivityClass.SECRET,
        max_supported_version=_OAUTH_TOKEN_VERSION,
    )
    if record is None:
        return None
    return record.payload.decode("utf-8")


def save_oauth_token_cache(token_path: Path, payload: str) -> None:
    """Persist OAuth token JSON as a SECRET-class secure object."""

    SecureObjectRepository().save(
        namespace=_OAUTH_TOKEN_NAMESPACE,
        object_key=_oauth_token_key(token_path),
        classification=SensitivityClass.SECRET,
        schema_version=_OAUTH_TOKEN_VERSION,
        written_at=datetime.now(UTC),
        payload=payload.encode("utf-8"),
    )


def delete_oauth_token_cache(token_path: Path) -> bool:
    """Delete the encrypted OAuth token cache for ``token_path``."""

    return SecureObjectRepository().delete(_OAUTH_TOKEN_NAMESPACE, _oauth_token_key(token_path))


def _oauth_token_key(token_path: Path) -> str:
    return Path(token_path).expanduser().as_posix()


def google_oauth_client_cache_exists(client_path: Path) -> bool:
    """Return whether an encrypted OAuth client JSON payload exists."""

    return SecureObjectRepository().exists(_OAUTH_CLIENT_NAMESPACE, _secure_path_key(client_path))


def load_google_oauth_client_json(client_path: Path) -> str | None:
    """Load encrypted Google OAuth client JSON for ``client_path``."""

    record = SecureObjectRepository().load(
        _OAUTH_CLIENT_NAMESPACE,
        _secure_path_key(client_path),
        expected_class=SensitivityClass.SECRET,
        max_supported_version=_OAUTH_CLIENT_VERSION,
    )
    if record is None:
        return None
    return record.payload.decode("utf-8")


def save_google_oauth_client_json(client_path: Path, payload: str) -> None:
    """Persist Google OAuth client JSON as a SECRET-class secure object."""

    SecureObjectRepository().save(
        namespace=_OAUTH_CLIENT_NAMESPACE,
        object_key=_secure_path_key(client_path),
        classification=SensitivityClass.SECRET,
        schema_version=_OAUTH_CLIENT_VERSION,
        written_at=datetime.now(UTC),
        payload=payload.encode("utf-8"),
    )


def google_service_account_cache_exists(key_path: Path) -> bool:
    """Return whether an encrypted service-account JSON payload exists."""

    return SecureObjectRepository().exists(_SERVICE_ACCOUNT_NAMESPACE, _secure_path_key(key_path))


def load_google_service_account_json(key_path: Path) -> str | None:
    """Load encrypted Google service-account JSON for ``key_path``."""

    record = SecureObjectRepository().load(
        _SERVICE_ACCOUNT_NAMESPACE,
        _secure_path_key(key_path),
        expected_class=SensitivityClass.SECRET,
        max_supported_version=_SERVICE_ACCOUNT_VERSION,
    )
    if record is None:
        return None
    return record.payload.decode("utf-8")


def save_google_service_account_json(key_path: Path, payload: str) -> None:
    """Persist Google service-account JSON as a SECRET-class secure object."""

    SecureObjectRepository().save(
        namespace=_SERVICE_ACCOUNT_NAMESPACE,
        object_key=_secure_path_key(key_path),
        classification=SensitivityClass.SECRET,
        schema_version=_SERVICE_ACCOUNT_VERSION,
        written_at=datetime.now(UTC),
        payload=payload.encode("utf-8"),
    )


def _secure_path_key(path: Path) -> str:
    return Path(path).expanduser().resolve().as_posix()


def inspect_google_auth(settings: Settings, *, project_root: Path) -> GoogleAuthInspection:
    """Inspect local Google-auth state without triggering browser auth flows.

    Resolves the active :class:`GoogleAuthPath` deterministically from
    ``settings`` plus on-disk material. When ``settings.google_auth_path``
    is set, that explicit selection is honoured even if the backing
    material is incomplete (the failure is reported via
    :attr:`GoogleAuthInspection.blocking_reason`); when nothing is
    configured, the resolver picks whichever path is fully provisioned
    and reports ambiguity when both families are present.

    Args:
        settings: The active :class:`aeat.core.config.Settings` snapshot
            providing OAuth client material, service-account paths, and
            the token-cache directory.
        project_root: Repository root used to resolve the workspace MCP
            credentials directory.

    Returns:
        A frozen :class:`GoogleAuthInspection` describing the resolved
        active path, every consulted input, and any blocking issues.
    """

    configured_path = normalize_google_auth_path(settings.google_auth_path)
    desktop_oauth_json_path = Path(settings.google_oauth_client_json) if settings.google_oauth_client_json else None
    desktop_oauth_secure_complete = desktop_oauth_json_path is not None and google_oauth_client_cache_exists(
        desktop_oauth_json_path
    )
    desktop_oauth_complete = bool(settings.google_oauth_client_id and settings.google_oauth_client_secret) or bool(
        desktop_oauth_secure_complete
    )
    desktop_oauth_partial = (
        bool(
            settings.google_oauth_client_id or settings.google_oauth_client_secret or settings.google_oauth_client_json
        )
        and not desktop_oauth_complete
    )
    service_account_configured_path = (
        Path(settings.google_application_credentials) if settings.google_application_credentials else None
    )
    service_account_existing_path = None
    if service_account_configured_path and (
        service_account_configured_path.exists() or google_service_account_cache_exists(service_account_configured_path)
    ):
        service_account_existing_path = service_account_configured_path

    active_path: GoogleAuthPath | None = None
    blocking_reason: str | None = None

    if configured_path is not None:
        active_path = configured_path
        if configured_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV and not desktop_oauth_complete:
            blocking_reason = (
                "GOOGLE_AUTH_PATH selects Desktop OAuth local-dev but GOOGLE_OAUTH_CLIENT_ID/SECRET are incomplete."
            )
        elif configured_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION and service_account_existing_path is None:
            if service_account_configured_path is None:
                blocking_reason = (
                    "GOOGLE_AUTH_PATH selects Service-account automation but GOOGLE_APPLICATION_CREDENTIALS is unset."
                )
            else:
                blocking_reason = (
                    "GOOGLE_AUTH_PATH selects Service-account automation but the configured key file does not exist."
                )
    else:
        if desktop_oauth_complete and service_account_existing_path is not None:
            blocking_reason = (
                "Both Desktop OAuth local-dev and Service-account automation are configured. "
                "Set GOOGLE_AUTH_PATH to choose the active path."
            )
        elif desktop_oauth_complete:
            active_path = GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
        elif service_account_existing_path is not None:
            active_path = GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION
        elif desktop_oauth_partial:
            blocking_reason = "Desktop OAuth local-dev is partially configured. Complete GOOGLE_OAUTH_CLIENT_ID/SECRET."
        elif service_account_configured_path is not None:
            blocking_reason = "Service-account automation is configured but the key file does not exist."
        else:
            blocking_reason = (
                "No Google auth path is configured. Initialize Desktop OAuth local-dev or Service-account automation."
            )

    return GoogleAuthInspection(
        configured_path=configured_path,
        active_path=active_path,
        desktop_oauth_complete=desktop_oauth_complete,
        desktop_oauth_partial=desktop_oauth_partial,
        desktop_oauth_json_path=desktop_oauth_json_path,
        service_account_configured_path=service_account_configured_path,
        service_account_existing_path=service_account_existing_path,
        oauth_token_path=settings.aeat_token_dir / "google_oauth_token.json",
        mcp_credentials_dir=project_root / "env" / "workspace-mcp-credentials",
        adc_path=adc_well_known_path(),
        oauth_token_issue=inspect_oauth_token_cache(settings.aeat_token_dir / "google_oauth_token.json"),
        blocking_reason=blocking_reason,
    )
