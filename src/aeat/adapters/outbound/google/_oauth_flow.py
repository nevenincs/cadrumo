"""Google OAuth Desktop login flow for per-profile Google sessions.

Runs an operator-supplied :class:`OAuthClient` through Google's loopback
IP + PKCE Desktop flow using
``google_auth_oauthlib.flow.InstalledAppFlow.run_local_server(port=0)``.
The operating system picks an ephemeral loopback port and opens the
consent screen in the operator's default browser.

Two policy gates fire before any network IO happens:

1. The caller must pass a profile identity resolved by
   :func:`aeat.adapters.outbound.google._active_profile.resolve_active_profile`.
2. When :class:`~aeat.core.config.SecretStoreBackend` is configured as
   ``UNSECURED`` and that profile carries a real Spanish NIF / NIE / CIF,
   :func:`check_unsecured_mode_safety` refuses with
   :class:`GoogleAuthUnsecuredModeRefusedError`.

See Also:
    :func:`run_login_flow` executes the login path,
    :func:`credentials_to_records` produces :class:`OAuthToken` and
    :class:`OAuthMetadata`, and :data:`REQUIRED_SCOPES` defines the consent
    surface the Google account must grant.
"""

from __future__ import annotations

import sys
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
    GoogleAuthNonInteractiveError,
    GoogleAuthProfileUnboundError,
    GoogleAuthScopeInsufficientError,
    GoogleAuthUnsecuredModeRefusedError,
)
from ._records import REQUIRED_SCOPES, OAuthClient, OAuthMetadata, OAuthToken

# Upper bound (seconds) on how long the loopback consent receiver blocks
# waiting for the operator to complete the browser flow. Defence in depth
# behind ``require_interactive_terminal``: even when a TTY is present the
# flow must not block indefinitely if the operator abandons consent.
_CONSENT_WAIT_TIMEOUT_SECONDS = 300


def require_interactive_terminal() -> None:
    """Refuse the consent flow when no controlling terminal can drive it.

    The Desktop OAuth flow opens the consent screen in the operator's
    browser and then blocks a loopback HTTP receiver until consent
    completes. In a non-interactive invocation (piped, redirected, cron,
    or another agent) ``stdin`` is not a TTY, no operator can complete the
    flow, and the receiver would block forever. This guard eliminates that
    silent-hang failure mode before :func:`run_login_flow` calls the local
    server.

    Raises:
        :class:`GoogleAuthNonInteractiveError`: When ``sys.stdin`` is not
            attached to a terminal. The exception carries the
            interactive-terminal prerequisite as a suggestion.
    """
    stdin = sys.stdin
    isatty = getattr(stdin, "isatty", None)
    if stdin is None or isatty is None or not isatty():
        raise GoogleAuthNonInteractiveError(
            "google OAuth refused: interactive browser consent requires a controlling terminal",
            context={"reason": "stdin_not_a_tty"},
            suggestion=tr("adapters.google.oauth_flow.suggestions.run_from_interactive_terminal"),
            translated_message="adapters.google.oauth_flow.errors.non_interactive",
        )


def check_unsecured_mode_safety(profile: str, tax_id: str) -> None:
    """Refuse the OAuth flow when unsecured mode meets a real NIF.

    The guard mirrors the storage substrate's NIF-canary rule: real taxpayer
    identifiers must not enter OAuth token setup while
    :class:`~aeat.core.config.SecretStoreBackend` is running in unsecured mode.

    Args:
        profile: Active profile UUID resolved by
            :func:`aeat.adapters.outbound.google._active_profile.resolve_active_profile`.
        tax_id: The active profile's ``identity.tax_id`` value. Empty string
            when the profile has no stored tax identifier.

    Raises:
        :class:`GoogleAuthUnsecuredModeRefusedError`: When
            ``aeat_secret_store_backend=unsecured`` and ``tax_id`` parses as a
            real Spanish tax identifier per
            :func:`~aeat.adapters.persistence.storage.master_key.looks_like_real_tax_id`.
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
    """Return the ``identity.tax_id`` value for the profile UUID.

    ``profile_id`` is the immutable profile identity returned by
    :func:`aeat.adapters.outbound.google._active_profile.resolve_active_profile`.
    The resolver loads the profile bucket pointer through
    :func:`aeat.application.workflow.read_profile_bucket_by_id`, opens the
    canonical user-profile lifecycle service, and reads the tax-id fact used
    by :func:`check_unsecured_mode_safety`.

    Returns:
        The stored ``identity.tax_id`` value, or an empty string when the
        profile record has no tax identifier.

    Raises:
        :class:`GoogleAuthProfileUnboundError`: When the profile bucket
            manifest or canonical profile record cannot be resolved.
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
    """Map OAuth credential fields into persisted Google session records.

    The consent screen must grant every scope in :data:`REQUIRED_SCOPES`.
    The returned :class:`OAuthToken` carries the refresh credential and the
    returned :class:`OAuthMetadata` carries the linked Google account, granted
    scope tuple, and issuance timestamps used by the session store.

    Args:
        refresh_token: The refresh token returned by the consent screen.
        token_uri: The token endpoint URL mirrored from :class:`OAuthClient`.
        account_email: The Google account that completed the consent.
        granted_scopes: Scopes the consent screen actually granted.
        issued_at: Timestamp the credential was first issued.

    Returns:
        A 2-tuple of (:class:`OAuthToken`, :class:`OAuthMetadata`) ready for
        :class:`~aeat.adapters.persistence.storage.sql.SecureObjectRepository`
        persistence through :mod:`aeat.adapters.outbound.google._session_store`.
        Both records validate strict pydantic invariants; metadata refuses
        granted-scope tuples missing any :data:`REQUIRED_SCOPES` member.

    Raises:
        :class:`GoogleAuthScopeInsufficientError`: When ``granted_scopes``
            omits any required scope. Re-raised separately from the pydantic
            ``ValidationError`` so the CLI can surface a
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

    Always runs the real
    ``google_auth_oauthlib.flow.InstalledAppFlow.run_local_server(port=0)``
    against ``accounts.google.com``. The flow checks profile state with
    :func:`resolve_active_tax_id`, applies :func:`check_unsecured_mode_safety`,
    requires :func:`require_interactive_terminal`, then maps the resulting
    credential fields through :func:`credentials_to_records`.

    Args:
        client: Operator-imported Desktop OAuth client metadata.
        profile: Active profile UUID resolved by
            :func:`aeat.adapters.outbound.google._active_profile.resolve_active_profile`.

    Returns:
        A 2-tuple of (:class:`OAuthToken`, :class:`OAuthMetadata`) ready for persistence.

    Raises:
        :class:`~aeat.adapters.outbound.google._errors.GoogleAuthError`: Any
            typed OAuth refusal with concrete remediation context.
    """
    check_unsecured_mode_safety(profile, resolve_active_tax_id(profile))
    # Gate the blocking loopback consent receiver: refuse fast in a
    # non-interactive shell rather than hang forever waiting for a browser
    # redirect no operator can complete. Placed after the profile / unsecured
    # gates so their more-specific refusals take precedence, and immediately
    # before the only call that would block.
    require_interactive_terminal()
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

    Imports ``google_auth_oauthlib`` lazily so the failure mode of a
    missing transitive dependency surfaces as a typed
    :class:`GoogleAuthNetworkError` rather than an opaque ``ImportError``.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GoogleAuthNetworkError(
            f"google-auth-oauthlib not importable: {exc}",
            suggestion="pip install aeat[google]",
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
        credentials = flow.run_local_server(port=0, timeout_seconds=_CONSENT_WAIT_TIMEOUT_SECONDS)
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
    """Translate upstream local-server OAuth failures into the Google auth hierarchy."""
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
    """Verify the ID token and return the ``email`` claim.

    Follows Google's OpenID Connect verification guidance:
    https://developers.google.com/identity/openid-connect/openid-connect#validatinganidtoken

    Verification requires the audience (our OAuth client_id) to match
    the token's ``aud`` claim. :data:`REQUIRED_SCOPES` must include the
    ``openid`` + ``userinfo.email`` pair for Google to include the ``email``
    claim in the ID token.

    Args:
        credentials: Google credentials object carrying ``id_token`` and ``scopes``.
        audience: OAuth client ID used as the expected ``aud`` claim.

    Returns:
        The verified email address extracted from the ID token payload.

    Raises:
        :class:`GoogleAuthScopeInsufficientError`: When the credential carries
            no ``id_token`` or the verified payload has no ``email`` claim.
        :class:`GoogleAuthNetworkError`: When ``google.oauth2.id_token`` is not
            importable or the verification HTTP fetch fails.
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
            suggestion="pip install aeat[google]",
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
    "require_interactive_terminal",
    "resolve_active_tax_id",
    "run_login_flow",
]
