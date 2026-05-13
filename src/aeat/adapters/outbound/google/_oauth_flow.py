"""Google OAuth Desktop login flow.

Runs the operator-supplied Cloud Console Desktop OAuth client through
the loopback IP + PKCE flow defined by Google's OAuth 2.0 for
Installed Applications guide. The implementation uses
`google_auth_oauthlib.flow.InstalledAppFlow.run_local_server(port=0)`
so the OS picks an ephemeral loopback port and the consent screen
opens in the operator's default browser.

Two policy gates fire before any network IO happens:

1. The active profile must be bound (resolver in `_profile_binding`).
2. If the secret store is running in `unsecured` mode AND the active
   profile carries a real Spanish NIF / NIE / CIF, the flow refuses
   with `GoogleAuthUnsecuredModeRefusedError`. This mirrors the
   substrate's existing NIF-canary behaviour.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from ....adapters.persistence.storage.master_key._master_key import looks_like_real_tax_id
from ....application.profile._repository import profile_bucket_repository
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import SecretStoreBackend, load_settings
from ._errors import (
    GoogleAuthBrowserOpenError,
    GoogleAuthLoopbackBindError,
    GoogleAuthNetworkError,
    GoogleAuthScopeInsufficientError,
    GoogleAuthUnsecuredModeRefusedError,
)
from ._records import REQUIRED_SCOPES, OAuthClient, OAuthMetadata, OAuthToken


def check_unsecured_mode_safety(profile: str, tax_id: str) -> None:
    """Refuse the OAuth flow when unsecured mode meets a real NIF.

    Args:
        profile: Resolved active profile name (per `_profile_binding`).
        tax_id: The active profile's `tax.id` value. Empty string when
            the profile has no tax id stored.

    Raises:
        GoogleAuthUnsecuredModeRefusedError: When
            `aeat_secret_store_backend=unsecured` AND `tax_id` parses
            as a real Spanish tax identifier per `looks_like_real_tax_id`.
    """

    settings = load_settings()
    if settings.aeat_secret_store_backend is not SecretStoreBackend.UNSECURED:
        return
    cleaned = tax_id.strip()
    if cleaned and looks_like_real_tax_id(cleaned):
        raise GoogleAuthUnsecuredModeRefusedError(
            "google OAuth refused: secret store is unsecured and the active profile carries a real NIF",
            context={"profile": profile, "backend": "unsecured"},
            suggestion="set aeat_secret_store_backend=keyring or use a synthetic test NIF",
        )


def resolve_active_tax_id(profile: str) -> str:
    """Return the `tax.id` value for the named profile, or empty string.

    Looks up the workflow state's pointer for `profile`, loads the
    secure profile bucket, and reads `record.values["tax.id"]`. Used by
    the orchestrator to feed `check_unsecured_mode_safety`.
    """

    state = workflow_state_repository().load()
    pointer = state.profiles.get(profile)
    if pointer is None:
        return ""
    record = profile_bucket_repository().load(pointer.bucket_id)
    if record is None:
        return ""
    return str(record.values.get("tax.id", ""))


def credentials_to_records(
    *,
    refresh_token: str,
    token_uri: str,
    account_email: str,
    granted_scopes: tuple[str, ...],
    issued_at: datetime,
) -> tuple[OAuthToken, OAuthMetadata]:
    """Map a `google.oauth2.credentials.Credentials` triple into our records.

    Args:
        refresh_token: The refresh token returned by the consent screen.
        token_uri: The token endpoint URL (mirrors the OAuth client).
        account_email: The Google account that completed the consent.
        granted_scopes: Scopes the consent screen actually granted.
        issued_at: Timestamp the credential was first issued.

    Returns:
        A `(OAuthToken, OAuthMetadata)` pair ready for SecureObjectRepository
        persistence. Both records validate strict pydantic invariants;
        the metadata refuses tuples missing `drive.file` or `spreadsheets`.

    Raises:
        GoogleAuthScopeInsufficientError: When `granted_scopes` omits
            either required scope. Re-raised separately from the
            pydantic `ValidationError` so the CLI can surface a
            concrete remediation hint.
    """

    missing = tuple(scope for scope in REQUIRED_SCOPES if scope not in granted_scopes)
    if missing:
        raise GoogleAuthScopeInsufficientError(
            f"consent screen returned without granting required scopes: {missing!r}",
            context={"missing_scopes": list(missing), "account_email": account_email},
            suggestion="aeat config google login",
        )
    token = OAuthToken(refresh_token=refresh_token, token_uri=token_uri)
    metadata = OAuthMetadata(
        account_email=account_email,
        granted_scopes=tuple(granted_scopes),
        issued_at=issued_at,
        last_refresh_at=issued_at,
    )
    return token, metadata


def run_login_flow(
    client: OAuthClient,
    profile: str,
    *,
    flow_runner: Callable[[OAuthClient], tuple[str, str, str, tuple[str, ...]]] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[OAuthToken, OAuthMetadata]:
    """Execute the loopback-IP + PKCE OAuth Desktop flow.

    Args:
        client: The operator-imported OAuth client metadata.
        profile: Resolved active profile name (per `_profile_binding`).
        flow_runner: Test seam. When `None`, the real
            `google_auth_oauthlib.flow.InstalledAppFlow.run_local_server(port=0)`
            executes. The runner receives the client and returns
            `(refresh_token, token_uri, account_email, granted_scopes)`.
        clock: Test seam producing `issued_at`. Defaults to `datetime.now(timezone.utc)`.

    Returns:
        A `(OAuthToken, OAuthMetadata)` pair ready for persistence.

    Raises:
        GoogleAuthUnsecuredModeRefusedError: Per `check_unsecured_mode_safety`.
        GoogleAuthScopeInsufficientError: Per `credentials_to_records`.
        GoogleAuthLoopbackBindError: When the loopback HTTP receiver
            fails to bind a port (typically port-exhaustion in CI).
        GoogleAuthBrowserOpenError: When the OS launcher refuses to
            open the consent URL (typically headless environments).
        GoogleAuthNetworkError: When the OAuth or token endpoint is
            unreachable.
    """

    check_unsecured_mode_safety(profile, resolve_active_tax_id(profile))
    runner = flow_runner if flow_runner is not None else _real_run_local_server
    now = clock if clock is not None else _utc_now
    refresh_token, token_uri, account_email, granted_scopes = runner(client)
    return credentials_to_records(
        refresh_token=refresh_token,
        token_uri=token_uri,
        account_email=account_email,
        granted_scopes=granted_scopes,
        issued_at=now(),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _real_run_local_server(client: OAuthClient) -> tuple[str, str, str, tuple[str, ...]]:
    """Real loopback-IP + PKCE OAuth Desktop flow runner.

    Imported lazily so the test seam path does not import
    `google_auth_oauthlib` (heavyweight). The error-class translation
    layer maps the common upstream failure modes onto our typed
    `GoogleAuthError` subclasses.
    """

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GoogleAuthNetworkError(
            f"google-auth-oauthlib not importable: {exc}",
            suggestion="uv sync",
        ) from exc

    client_config: dict[str, dict[str, object]] = {
        "installed": {
            "client_id": client.client_id,
            "client_secret": client.client_secret,
            "project_id": client.project_id,
            "auth_uri": client.auth_uri,
            "token_uri": client.token_uri,
            "auth_provider_x509_cert_url": client.auth_provider_x509_cert_url,
            "redirect_uris": list(client.redirect_uris) or ["http://localhost"],
        }
    }
    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=list(REQUIRED_SCOPES))
    except ValueError as exc:
        raise GoogleAuthNetworkError(f"OAuth client config refused: {exc}") from exc

    try:
        credentials = flow.run_local_server(port=0)
    except OSError as exc:
        raise GoogleAuthLoopbackBindError(
            f"loopback receiver failed to bind: {exc}",
            suggestion="close the application holding a stray loopback port and retry",
        ) from exc
    except Exception as exc:
        message = str(exc).lower()
        if "browser" in message or "webbrowser" in message:
            raise GoogleAuthBrowserOpenError(
                f"OS browser launcher refused: {exc}",
                suggestion="open the printed consent URL manually in your browser",
            ) from exc
        if "transport" in message or "connect" in message or "network" in message:
            raise GoogleAuthNetworkError(f"OAuth endpoint unreachable: {exc}") from exc
        raise

    return (
        str(credentials.refresh_token),
        str(credentials.token_uri),
        str(getattr(credentials, "id_token_email", "") or _decode_email_from_id_token(credentials)),
        tuple(str(scope) for scope in (credentials.scopes or ())),
    )


def _decode_email_from_id_token(credentials: object) -> str:
    """Best-effort email extraction from an ID-token payload."""

    id_token_jwt = getattr(credentials, "id_token", None)
    if id_token_jwt is None:
        return ""
    try:
        from google.auth.transport import requests as auth_requests
        from google.oauth2 import id_token as id_token_module
    except ImportError:
        return ""
    try:
        payload = id_token_module.verify_oauth2_token(id_token_jwt, auth_requests.Request())
    except (ValueError, AttributeError):
        return ""
    return str(payload.get("email", ""))


__all__ = [
    "check_unsecured_mode_safety",
    "credentials_to_records",
    "resolve_active_tax_id",
    "run_login_flow",
]
