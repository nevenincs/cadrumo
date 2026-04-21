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
from typing import TYPE_CHECKING, Any

import google.auth
from google.auth.credentials import Credentials as BaseCredentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ._authenticator import AeatAuthenticator
from ._browser import (
    BrowserContextLike,
    BrowserPageLike,
    BrowserResponseLike,
    BrowserSessionFactory,
    BrowserSessionLike,
)
from ._gate import AeatAccessGate, AeatGateEnvSnapshot
from ._models import (
    AEAT_SESSION_IDLE_TTL,
    AeatLoginAssertion,
    AeatSession,
    CertificateSessionDetail,
)
from ._protocols import AuthProviderDescription, AuthProviderKind
from ._providers._certificate._certificate_backends._playwright_context import (
    build_client_certificates_kwarg,
)
from ._providers._certificate.certificate import (
    AeatLiveReadNotEnabledError,
    AeatLoginAssertionError,
    AeatSessionExpiredError,
    CertificateBackend,
    CertificateBundle,
    CertificateError,
    CertificateExpiredError,
    CertificateHandshakeError,
    CertificateHealth,
    CertificateHealthSeverity,
    CertificateLoadError,
    CertificateNifParseError,
    CertificatePasswordError,
    CertificatePreExpiryError,
    HandshakeResult,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
    health,
    load_certificate,
    preload_into_browser_context,
    verify_handshake,
)

if TYPE_CHECKING:
    from ..config import Settings

__all__ = [
    "AEAT_SESSION_IDLE_TTL",
    "AeatAccessGate",
    "AeatAuthenticator",
    "AeatGateEnvSnapshot",
    "AeatLiveReadNotEnabledError",
    "AeatLoginAssertion",
    "AeatLoginAssertionError",
    "AeatSession",
    "AeatSessionExpiredError",
    "AuthProviderDescription",
    "AuthProviderKind",
    "BrowserContextLike",
    "BrowserPageLike",
    "BrowserResponseLike",
    "BrowserSessionFactory",
    "BrowserSessionLike",
    "CertificateBackend",
    "CertificateBundle",
    "CertificateError",
    "CertificateExpiredError",
    "CertificateHandshakeError",
    "CertificateHealth",
    "CertificateHealthSeverity",
    "CertificateLoadError",
    "CertificateNifParseError",
    "CertificatePasswordError",
    "CertificatePreExpiryError",
    "CertificateSessionDetail",
    "HandshakeResult",
    "LoadedCertificate",
    "build_client_certificates_kwarg",
    "evaluate_loaded_certificate_health",
    "extract_nif_from_subject",
    "health",
    "load_certificate",
    "preload_into_browser_context",
    "verify_handshake",
]

log = logging.getLogger(__name__)

# ── Scope constants ─────────────────────────────────────────────────────────
# Default: full read/write access to Drive, Sheets, Docs, and Cloud Platform.
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DOCS_SCOPE = "https://www.googleapis.com/auth/documents"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
USERINFO_EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
OPENID_SCOPE = "openid"

# The full default scope set covering Workspace + GCP admin.
SCOPES: list[str] = [
    DRIVE_SCOPE,
    SHEETS_SCOPE,
    DOCS_SCOPE,
    CLOUD_PLATFORM_SCOPE,
    USERINFO_EMAIL_SCOPE,
    OPENID_SCOPE,
]

# Scopes the bootstrap insists on at ADC acquisition time. The doctor
# verifies that the on-disk ADC JSON has every scope in this list.
REQUIRED_ADC_SCOPES: list[str] = [
    DRIVE_SCOPE,
    SHEETS_SCOPE,
    DOCS_SCOPE,
    CLOUD_PLATFORM_SCOPE,
    USERINFO_EMAIL_SCOPE,
]

# Narrower scope sets for least-privilege usage.
DRIVE_READONLY_SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.readonly"]
SHEETS_READONLY_SCOPES: list[str] = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
DOCS_READONLY_SCOPES: list[str] = ["https://www.googleapis.com/auth/documents.readonly"]
DRIVE_FILE_SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.file"]
STORAGE_FULL_CONTROL_SCOPE = "https://www.googleapis.com/auth/devstorage.full_control"
STORAGE_READ_ONLY_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"


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
    """Build an authenticated Google Drive API v3 client.

    The discovery cache is disabled because intermittent cache corruption
    is a long-standing source of test flakes. Each build performs one
    extra discovery round-trip; we accept the cost.
    """
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def build_sheets_service(credentials: BaseCredentials) -> Any:
    """Build an authenticated Google Sheets API v4 client."""
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def build_docs_service(credentials: BaseCredentials) -> Any:
    """Build an authenticated Google Docs API v1 client."""
    return build("docs", "v1", credentials=credentials, cache_discovery=False)


def build_serviceusage_service(credentials: BaseCredentials) -> Any:
    """Build an authenticated Service Usage API v1 client.

    Used by `aeat doctor` to check API enablement state without shelling
    out to gcloud.
    """
    return build("serviceusage", "v1", credentials=credentials, cache_discovery=False)


def build_storage_client(credentials: BaseCredentials, project: str) -> Any:
    """Build a typed Google Cloud Storage client.

    Args:
        credentials: Authenticated Google credentials.
        project: GCP project ID for billing and quota.

    Returns:
        A ``google.cloud.storage.Client`` instance.
    """
    from google.cloud import storage  # local import to avoid hard dep at module load

    return storage.Client(project=project, credentials=credentials)


def build_cloudfunctions_client(credentials: BaseCredentials) -> Any:
    """Build a typed Cloud Functions v2 client."""
    from google.cloud import functions_v2

    return functions_v2.FunctionServiceClient(credentials=credentials)


def build_cloudrun_client(credentials: BaseCredentials) -> Any:
    """Build a typed Cloud Run v2 services client."""
    from google.cloud import run_v2

    return run_v2.ServicesClient(credentials=credentials)


# ── Scope verification helpers ──────────────────────────────────────────────


def assert_credentials_have_scopes(
    credentials: object,
    required: list[str],
) -> tuple[bool, list[str]]:
    """Check whether a credentials-like object covers a required scope set.

    Duck-typed on the ``scopes`` attribute so the helper can be used
    against real google-auth credential objects, ADC dict payloads, or
    any test stand-in that exposes a ``scopes`` iterable. Returns the
    verdict alongside the list of missing scopes so callers can render
    targeted remediation hints rather than a single boolean.

    Args:
        credentials: Any object exposing a ``scopes`` attribute.
        required: Scopes that must be granted.

    Returns:
        A ``(ok, missing)`` tuple. ``ok`` is True iff every required
        scope is present in the credentials' scope set. ``missing`` is
        the sorted list of scopes the credentials lack.
    """
    granted = set(getattr(credentials, "scopes", None) or [])
    missing = sorted(set(required) - granted)
    return (not missing, missing)


def get_adc_credentials_with_scopes(scopes: list[str] | None = None) -> BaseCredentials:
    """Return Application Default Credentials, requesting the given scopes.

    Wraps ``google.auth.default(scopes=...)`` and re-raises with a clearer
    message if no ADC are configured. Does not perform any browser flow —
    the caller must have already run ``gcloud auth application-default
    login`` with at least the scopes requested here.

    Args:
        scopes: Scopes to attach to the returned credentials. Defaults
            to the full ``SCOPES`` set.

    Returns:
        Authenticated credentials suitable for any Google API client.

    Raises:
        google.auth.exceptions.DefaultCredentialsError: If ADC are not
            configured on the workstation.
    """
    scopes = scopes or SCOPES
    credentials, _project = google.auth.default(scopes=scopes)
    return credentials


def get_credentials_for_scopes(scopes: list[str] | None = None) -> BaseCredentials:
    """Return credentials for the requested scopes via the configured auth path.

    Resolution order, identical to :func:`get_credentials` but cleaner
    to call from CLI commands and live tests because it doesn't require
    the caller to pre-load Settings:

    1. Service account if ``GOOGLE_APPLICATION_CREDENTIALS`` points at
       a readable JSON key file.
    2. OAuth 2.0 Desktop installed-app flow if both
       ``GOOGLE_OAUTH_CLIENT_ID`` and ``GOOGLE_OAUTH_CLIENT_SECRET`` are
       set in the environment.
    3. Application Default Credentials via
       ``gcloud auth application-default login``.

    The unified resolver is the entry point every CLI command should
    use, so the active auth path is decided in one place and Settings
    edits propagate without per-call wiring.

    Args:
        scopes: Scopes to request. Defaults to the full :data:`SCOPES`
            set.

    Returns:
        Authenticated credentials suitable for any Google API client.
    """
    from ..config import Settings  # local import to avoid import cycle

    scopes = scopes or SCOPES
    settings = Settings()
    return get_credentials(settings, scopes=scopes)
