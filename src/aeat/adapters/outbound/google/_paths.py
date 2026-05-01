"""Shared Google-auth path inspection and deterministic selection logic."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....core.config import Settings


class GoogleAuthPath(StrEnum):
    """Named operator-facing Google auth paths supported by the repo."""

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


def adc_well_known_path() -> Path:
    """Return the well-known path where gcloud writes ADC JSON."""

    override = os.environ.get("CLOUDSDK_CONFIG")
    if override:
        return Path(override) / "application_default_credentials.json"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def normalize_google_auth_path(raw_path: object) -> GoogleAuthPath | None:
    """Normalize a config value into a supported Google auth path."""

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
    """Resolve a potentially repo-relative path against the current cwd."""

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return candidate.resolve()


@dataclass(frozen=True)
class GoogleAuthInspection:
    """Resolved Google-auth path plus the local material that backs it."""

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
        return self.active_path is None and self.blocking_reason is not None and "Both" in self.blocking_reason

    @property
    def oauth_token_exists(self) -> bool:
        return self.oauth_token_path.exists()

    @property
    def mcp_credentials_exist(self) -> bool:
        return self.mcp_credentials_dir.exists() and any(self.mcp_credentials_dir.iterdir())

    @property
    def mcp_credentials_dir_exists(self) -> bool:
        return self.mcp_credentials_dir.exists()

    @property
    def adc_exists(self) -> bool:
        return self.adc_path.exists()

    @property
    def inactive_path_drift(self) -> str | None:
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
        if self.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
            return self.desktop_oauth_complete and self.oauth_token_issue is None
        if self.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION:
            return self.service_account_existing_path is not None
        return False

    @property
    def mcp_ready(self) -> bool:
        if self.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
            return self.desktop_oauth_complete and self.mcp_credentials_exist
        if self.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION:
            return self.service_account_existing_path is not None and self.mcp_credentials_exist
        return False


def inspect_oauth_token_cache(token_path: Path) -> str | None:
    """Return ``None`` when the Desktop OAuth token cache looks usable."""

    if not token_path.exists():
        return "repo-local CLI OAuth token missing"
    try:
        payload = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"repo-local CLI OAuth token is unreadable: {exc.__class__.__name__}"
    if not isinstance(payload, dict):
        return "repo-local CLI OAuth token is malformed"
    refresh_token = payload.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        return "repo-local CLI OAuth token is missing a refresh_token"
    raw_scopes = payload.get("scopes")
    if not isinstance(raw_scopes, list):
        return "repo-local CLI OAuth token is missing its scope list"
    granted = {str(scope) for scope in raw_scopes}
    missing = sorted(set(DESKTOP_OAUTH_REQUIRED_SCOPES) - granted)
    if missing:
        missing_csv = ", ".join(missing)
        return f"repo-local CLI OAuth token is missing required scopes: {missing_csv}"
    return None


def inspect_google_auth(settings: Settings, *, project_root: Path) -> GoogleAuthInspection:
    """Inspect local Google-auth state without triggering browser auth flows."""

    configured_path = normalize_google_auth_path(settings.google_auth_path)
    desktop_oauth_complete = bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)
    desktop_oauth_partial = (
        bool(
            settings.google_oauth_client_id or settings.google_oauth_client_secret or settings.google_oauth_client_json
        )
        and not desktop_oauth_complete
    )
    desktop_oauth_json_path = Path(settings.google_oauth_client_json) if settings.google_oauth_client_json else None
    service_account_configured_path = (
        Path(settings.google_application_credentials) if settings.google_application_credentials else None
    )
    service_account_existing_path = None
    if service_account_configured_path and service_account_configured_path.exists():
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
