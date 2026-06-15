"""Google OAuth Desktop login flow.

Runs the operator-supplied Cloud Console Desktop OAuth client through
the loopback IP + PKCE flow defined by Google's OAuth 2.0 for
Installed Applications guide. The implementation uses
`google_auth_oauthlib.flow.InstalledAppFlow.run_local_server(port=0)`
so the OS picks an ephemeral loopback port and the consent screen
opens in the operator's default browser.

Two policy gates fire before any network IO happens:

1. The active profile must be bound (resolver in `_active_profile`).
2. If the secret store is running in `unsecured` mode AND the active
   profile carries a real Spanish NIF / NIE / CIF, the flow refuses
   with `GoogleAuthUnsecuredModeRefusedError`. This mirrors the
   substrate's existing NIF-canary behaviour.
"""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn

from ....adapters.persistence.storage.master_key import looks_like_real_tax_id
from ....core.config import SecretStoreBackend, load_settings
from ....core.i18n import tr
from ....core.time import now
from ....domain.user_profile import ProfileNotFoundError
from ._errors import (
    GoogleAuthBrowserOpenError,
    GoogleAuthLoopbackBindError,
    GoogleAuthNetworkError,
    GoogleAuthProfileUnboundError,
    GoogleAuthScopeInsufficientError,
    GoogleAuthUnsecuredModeRefusedError,
)
from ._records import REQUIRED_SCOPES, OAuthClient, OAuthMetadata, OAuthToken


def check_unsecured_mode_safety(profile: str, tax_id: str) -> None:
    """Refuse the OAuth flow when unsecured mode meets a real NIF.

    Args:
        profile: Resolved active profile UUID (per `_active_profile`).
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
            suggestion=tr("adapters.google.oauth_flow.suggestions.use_keyring_or_synthetic"),
            translated_message="adapters.google.oauth_flow.errors.unsecured_mode_refused",
        )


def resolve_active_tax_id(profile_id: str) -> str:
    """Return the `identity.tax_id` value for the profile UUID, or empty string.

    ``profile_id`` is the immutable UUID profile identity (per
    ``_active_profile.resolve_active_profile``). Loads the canonical
    user-profile record from that profile's bucket and reads the
    identity tax-id fact. Used by the orchestrator to feed
    `check_unsecured_mode_safety`.
    """
    from ....application.user_profile import build_lifecycle_service, fact_value
    from ....application.workflow import read_profile_bucket_by_id

    pointer = read_profile_bucket_by_id(profile_id)
    if pointer is None:
        raise GoogleAuthProfileUnboundError(
            "google OAuth refused: active profile bucket manifest could not be resolved",
            context={"profile": profile_id, "reason": "profile_bucket_manifest_missing"},
            suggestion=tr("adapters.google.oauth_flow.suggestions.repair_profile_state"),
            translated_message="adapters.google.oauth_flow.errors.profile_state_unresolved",
        )
    service = build_lifecycle_service(bucket_id=pointer.bucket_id)
    try:
        record = service.read(profile_id)
    except ProfileNotFoundError as exc:
        raise GoogleAuthProfileUnboundError(
            "google OAuth refused: active profile record could not be resolved",
            context={"profile": profile_id, "bucket_id": pointer.bucket_id, "reason": "profile_record_missing"},
            suggestion=tr("adapters.google.oauth_flow.suggestions.repair_profile_state"),
            translated_message="adapters.google.oauth_flow.errors.profile_state_unresolved",
        ) from exc
    return fact_value(record, "identity.tax_id") or ""


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
        A 2-tuple of (:class:`OAuthToken`, :class:`OAuthMetadata`) ready for
        SecureObjectRepository persistence. Both records validate strict
        pydantic invariants; the metadata refuses tuples missing
        ``drive.file`` or ``spreadsheets``.

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
            translated_message="adapters.google.oauth_flow.errors.scope_missing",
        )
    token = OAuthToken(refresh_token=refresh_token, token_uri=token_uri)
    metadata = OAuthMetadata(
        account_email=account_email,
        granted_scopes=tuple(granted_scopes),
        issued_at=issued_at,
        last_refresh_at=issued_at,
    )
    return token, metadata


def run_login_flow(client: OAuthClient, profile: str) -> tuple[OAuthToken, OAuthMetadata]:
    """Execute the loopback-IP + PKCE OAuth Desktop flow.

    Always runs the real `google_auth_oauthlib.flow.InstalledAppFlow.
    run_local_server(port=0)` against `accounts.google.com`. No test
    seams. Failure modes surface as typed `GoogleAuthError` subclasses
    with concrete remediation context.

    Args:
        client: The operator-imported OAuth client metadata.
        profile: Resolved active profile UUID (per `_active_profile`).

    Returns:
        A 2-tuple of (:class:`OAuthToken`, :class:`OAuthMetadata`) ready for persistence.
    """
    check_unsecured_mode_safety(profile, resolve_active_tax_id(profile))
    refresh_token, token_uri, account_email, granted_scopes = _run_local_server(client)
    return credentials_to_records(
        refresh_token=refresh_token,
        token_uri=token_uri,
        account_email=account_email,
        granted_scopes=granted_scopes,
        issued_at=now(),
    )


def _run_local_server(client: OAuthClient) -> tuple[str, str, str, tuple[str, ...]]:
    """Loopback-IP + PKCE OAuth Desktop flow runner.

    Imports `google_auth_oauthlib` lazily so the failure mode of a
    missing transitive dependency surfaces as a typed
    `GoogleAuthNetworkError` rather than an opaque ImportError.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GoogleAuthNetworkError(
            f"google-auth-oauthlib not importable: {exc}",
            suggestion="uv sync",
            translated_message="adapters.google.oauth_flow.errors.oauthlib_not_importable",
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
        },
    }
    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=list(REQUIRED_SCOPES))
    except ValueError as exc:
        raise GoogleAuthNetworkError(
            f"OAuth client config refused: {exc}",
            translated_message="adapters.google.oauth_flow.errors.client_config_refused",
        ) from exc

    try:
        credentials = flow.run_local_server(port=0)
    except OSError as exc:
        raise GoogleAuthLoopbackBindError(
            f"loopback receiver failed to bind: {exc}",
            suggestion=tr("adapters.google.oauth_flow.suggestions.close_loopback_port"),
            translated_message="adapters.google.oauth_flow.errors.loopback_bind_failed",
        ) from exc
    except Exception as exc:
        _raise_local_server_error(exc)

    # `google.oauth2.credentials.Credentials` exposes `token_uri` at runtime
    # but the `google-auth` stubs ship a narrower `Credentials` class on which
    # the attribute isn't visible to pyrefly. The dynamic lookup below is the
    # documented public API.
    token_uri = getattr(credentials, "token_uri", None)
    return (
        str(credentials.refresh_token),
        str(token_uri),
        _decode_email_from_id_token(credentials, audience=client.client_id),
        tuple(str(scope) for scope in (credentials.scopes or ())),
    )


def _raise_local_server_error(exc: Exception) -> NoReturn:
    """Translate upstream local-server OAuth failures into the GoogleAuth hierarchy."""
    message = str(exc).lower()
    if "browser" in message or "webbrowser" in message:
        raise GoogleAuthBrowserOpenError(
            f"OS browser launcher refused: {exc}",
            suggestion=tr("adapters.google.oauth_flow.suggestions.open_consent_url_manually"),
            translated_message="adapters.google.oauth_flow.errors.browser_launcher_refused",
        ) from exc
    if "transport" in message or "connect" in message or "network" in message:
        raise GoogleAuthNetworkError(
            f"OAuth endpoint unreachable: {exc}",
            translated_message="adapters.google.oauth_flow.errors.endpoint_unreachable",
        ) from exc
    raise GoogleAuthNetworkError(
        f"OAuth local server flow failed: {exc}",
        context={"error_type": type(exc).__name__},
        translated_message="adapters.google.oauth_flow.errors.endpoint_unreachable",
    ) from exc


def _decode_email_from_id_token(credentials: object, *, audience: str) -> str:
    """Verify the ID token and return the `email` claim.

    Follows Google's OpenID Connect verification guidance:
    https://developers.google.com/identity/openid-connect/openid-connect#validatinganidtoken

    Verification requires the audience (our OAuth client_id) to match
    the token's `aud` claim. The OAuth client must have requested the
    `openid` + `userinfo.email` scopes for Google to include the
    `email` claim in the id_token.

    Args:
        credentials: Google credentials object carrying ``id_token`` and ``scopes``.
        audience: OAuth client ID used as the expected ``aud`` claim.

    Returns:
        The verified email address extracted from the ID token payload.

    Raises:
        GoogleAuthScopeInsufficientError: When the credential carries no ``id_token``.
        GoogleAuthNetworkError: When ``google.oauth2.id_token`` is not importable
            or the verification HTTP fetch fails.
    """
    id_token_jwt = getattr(credentials, "id_token", None)
    if id_token_jwt is None:
        raise GoogleAuthScopeInsufficientError(
            "Google did not return an id_token; the OAuth consent did not include the openid+email scopes",
            context={"audience": audience},
            suggestion="aeat config google login",
            translated_message="adapters.google.oauth_flow.errors.id_token_missing",
        )
    try:
        from google.auth.transport import requests as auth_requests
        from google.oauth2 import id_token as id_token_module
    except ImportError as exc:
        raise GoogleAuthNetworkError(
            f"google-auth id_token module not importable: {exc}",
            suggestion="uv sync",
            translated_message="adapters.google.oauth_flow.errors.id_token_module_not_importable",
        ) from exc
    try:
        payload = id_token_module.verify_oauth2_token(id_token_jwt, auth_requests.Request(), audience)
    except ValueError as exc:
        raise GoogleAuthNetworkError(
            f"id_token verification failed: {exc}",
            context={"audience": audience},
            translated_message="adapters.google.oauth_flow.errors.id_token_verification_failed",
        ) from exc
    email = str(payload.get("email", ""))
    if not email:
        raise GoogleAuthScopeInsufficientError(
            "id_token verified but carries no `email` claim",
            context={"audience": audience},
            suggestion="aeat config google login",
            translated_message="adapters.google.oauth_flow.errors.email_claim_missing",
        )
    return email


__all__ = [
    "check_unsecured_mode_safety",
    "credentials_to_records",
    "resolve_active_tax_id",
    "run_login_flow",
]
