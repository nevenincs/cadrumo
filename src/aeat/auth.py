"""Google authentication and token management for AEAT automation.

Supports three authentication methods (resolved in priority order):

1. **Service Account** — headless/server use via GOOGLE_APPLICATION_CREDENTIALS.
   Best for automated pipelines and Cloud Functions.
2. **OAuth 2.0** — interactive desktop flow via client ID + secret.
   Best for development and user-delegated access.
3. **Application Default Credentials (ADC)** — fallback via
   ``gcloud auth application-default login``. Useful for local development
   without explicit credentials.

Token lifecycle
---------------
- OAuth tokens are cached in ``.tokens/google_oauth_token.json``.
- Expired tokens are refreshed automatically using the stored refresh token.
- Service account and ADC credentials manage their own token lifecycle.

Required API scopes
-------------------
The default scope set grants full read/write access to Drive and Sheets,
plus general Cloud Platform access for future Cloud Functions / Storage use.
Narrower scope constants are provided for least-privilege scenarios.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import google.auth
from google.auth.credentials import Credentials as BaseCredentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from aeat.config import Settings

log = logging.getLogger(__name__)

# ── Scope constants ─────────────────────────────────────────────────────────
# Default: full read/write access to Drive, Sheets, and Cloud Platform.
SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/cloud-platform",
]

# Narrower scope sets for least-privilege usage.
DRIVE_READONLY_SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.readonly"]
SHEETS_READONLY_SCOPES: list[str] = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
DRIVE_FILE_SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.file"]


# ── OAuth 2.0 ───────────────────────────────────────────────────────────────


def get_oauth_credentials(
    client_id: str,
    client_secret: str,
    *,
    scopes: list[str] | None = None,
    token_path: Path | None = None,
) -> OAuthCredentials:
    """Authenticate via OAuth 2.0 installed-app flow with persistent token cache.

    On first run, opens a browser for user consent. Subsequent calls reuse
    the cached token, refreshing it automatically when expired.

    Args:
        client_id: OAuth 2.0 client ID from Google Cloud Console.
        client_secret: OAuth 2.0 client secret.
        scopes: API scopes to request. Defaults to ``SCOPES``.
        token_path: Where to cache the OAuth token. Defaults to
            ``.tokens/google_oauth_token.json``.

    Returns:
        Authenticated OAuth credentials with a valid access token.
    """
    scopes = scopes or SCOPES
    token_path = token_path or Path(".tokens/google_oauth_token.json")
    creds: OAuthCredentials | None = None

    # 1. Try loading a cached token
    if token_path.exists():
        creds = OAuthCredentials.from_authorized_user_file(str(token_path), scopes)  # type: ignore[no-untyped-call]

    # 2. Refresh if expired, or run a new consent flow
    if creds and creds.expired and creds.refresh_token:
        log.info("Refreshing expired OAuth token")
        creds.refresh(Request())
    elif not creds or not creds.valid:
        log.info("Starting OAuth consent flow (browser will open)")
        client_config: dict[str, Any] = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, scopes)
        creds = flow.run_local_server(port=8080)

    # 3. Persist the token for next time
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())

    return creds


# ── Service Account ─────────────────────────────────────────────────────────


def get_service_account_credentials(
    key_path: str | Path,
    *,
    scopes: list[str] | None = None,
    subject: str | None = None,
) -> service_account.Credentials:
    """Load service-account credentials from a JSON key file.

    Args:
        key_path: Path to the service account JSON key file.
        scopes: API scopes to request. Defaults to ``SCOPES``.
        subject: Email of user to impersonate via domain-wide delegation.

    Returns:
        Authenticated service-account credentials.
    """
    scopes = scopes or SCOPES
    creds = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
        str(key_path),
        scopes=scopes,
    )
    if subject:
        creds = creds.with_subject(subject)
    return creds  # type: ignore[no-any-return]


# ── Credential resolver ────────────────────────────────────────────────────


def get_credentials(settings: Settings, *, scopes: list[str] | None = None) -> BaseCredentials:
    """Resolve credentials using the first available method.

    Resolution order:
        1. Service account — if ``GOOGLE_APPLICATION_CREDENTIALS`` points to a valid file.
        2. OAuth 2.0 — if ``GOOGLE_OAUTH_CLIENT_ID`` and ``GOOGLE_OAUTH_CLIENT_SECRET`` are set.
        3. Application Default Credentials — via ``gcloud auth application-default login``.

    Args:
        settings: Application settings (from ``load_settings()``).
        scopes: API scopes to request. Defaults to ``SCOPES``.

    Returns:
        Authenticated Google credentials ready for API calls.

    Raises:
        google.auth.exceptions.DefaultCredentialsError: If no credentials
            can be found via any method.
    """
    scopes = scopes or SCOPES

    # 1. Service account
    sa_path = settings.google_application_credentials
    if sa_path and Path(sa_path).exists():
        log.info("Using service account credentials from %s", sa_path)
        return get_service_account_credentials(
            sa_path,
            scopes=scopes,
            subject=settings.google_impersonate_email or None,
        )

    # 2. OAuth 2.0
    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        log.info("Using OAuth 2.0 credentials")
        token_path = settings.aeat_token_dir / "google_oauth_token.json"
        return get_oauth_credentials(
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
            scopes=scopes,
            token_path=token_path,
        )

    # 3. Application Default Credentials
    log.info("Falling back to Application Default Credentials")
    creds, _project = google.auth.default(scopes=scopes)
    return creds


# ── Service builders ────────────────────────────────────────────────────────


def build_drive_service(credentials: BaseCredentials) -> Any:
    """Build an authenticated Google Drive API v3 client."""
    return build("drive", "v3", credentials=credentials)


def build_sheets_service(credentials: BaseCredentials) -> Any:
    """Build an authenticated Google Sheets API v4 client."""
    return build("sheets", "v4", credentials=credentials)
