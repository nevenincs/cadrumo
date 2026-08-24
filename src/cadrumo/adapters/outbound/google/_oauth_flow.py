"""Google OAuth Desktop login flow for per-profile Google sessions.

Runs an operator-supplied :class:`adapters.outbound.google.OAuthClient`
through Google's loopback IP + PKCE Desktop flow using
``google_auth_oauthlib.flow.InstalledAppFlow.run_local_server(port=0)``.
The operating system picks an ephemeral loopback port and opens the
consent screen in the operator's default browser.

Two policy gates fire before any network IO happens:

1. The caller must pass a profile identity resolved by
   :func:`adapters.outbound.google.resolve_active_profile`.
2. When :class:`core.config.SecretStoreBackend` is configured as
   ``UNSECURED`` and that profile carries a real Spanish NIF / NIE / CIF,
   :func:`adapters.outbound.google._oauth_flow.check_unsecured_mode_safety`
   refuses with
   :exc:`adapters.outbound.google.GoogleAuthUnsecuredModeRefusedError`.

See Also:
    :func:`adapters.outbound.google.run_login_flow` executes the login
    path, :func:`adapters.outbound.google._oauth_flow.credentials_to_records`
    produces :class:`adapters.outbound.google.OAuthToken` and
    :class:`adapters.outbound.google.OAuthMetadata`, and
    :data:`adapters.outbound.google.REQUIRED_SCOPES` defines the consent
    surface the Google account must grant.
"""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn

from ....adapters.persistence.storage.master_key import looks_like_real_tax_id
from ....core import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.config import SecretStoreBackend, load_settings
from ....core.time import now
from ....core.tty import stdin_is_tty
from ....domain.user_profile import ProfileNotFoundError
from ._errors import (
    GoogleAuthBrowserOpenError,
    GoogleAuthLoopbackBindError,
    GoogleAuthNetworkError,
    GoogleAuthNonInteractiveError,
    GoogleAuthPreconditionCondition,
    GoogleAuthProfileUnboundError,
    GoogleAuthScopeInsufficientError,
    GoogleAuthUnsecuredModeRefusedError,
    google_auth_no_action_verdict,
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
    silent-hang failure mode before
    :func:`adapters.outbound.google.run_login_flow` calls the local server.

    Raises:
        :exc:`adapters.outbound.google.GoogleAuthNonInteractiveError`:
            When ``sys.stdin`` is not attached to a terminal.
    """
    if not stdin_is_tty():
        raise GoogleAuthNonInteractiveError(
            "google OAuth refused: interactive browser consent requires a controlling terminal",
            context={"reason": "stdin_not_a_tty"},
            translated_message="adapters.google.oauth_flow.errors.non_interactive",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.INTERACTIVE_TERMINAL_AVAILABLE,
                facts={"interactive_terminal_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )


def check_unsecured_mode_safety(profile: str, tax_id: str) -> None:
    """Refuse the OAuth flow when unsecured mode meets a real NIF.

    The guard mirrors the storage substrate's NIF-canary rule: real taxpayer
    identifiers must not enter OAuth token setup while
    :class:`core.config.SecretStoreBackend` is running in unsecured mode.

    Args:
        profile: Active profile UUID resolved by
            :func:`adapters.outbound.google.resolve_active_profile`.
        tax_id: The active profile's ``identity.tax_id`` value. Empty string
            when the profile has no stored tax identifier.

    Raises:
        :exc:`adapters.outbound.google.GoogleAuthUnsecuredModeRefusedError`:
            When
            ``cadrumo_secret_store_backend=unsecured`` and ``tax_id`` parses as a
            real Spanish tax identifier per
            :func:`adapters.persistence.storage.master_key.looks_like_real_tax_id`.
    """
    settings = load_settings()
    if settings.cadrumo_secret_store_backend is not SecretStoreBackend.UNSECURED:
        return
    cleaned = tax_id.strip()
    if cleaned and looks_like_real_tax_id(cleaned):
        raise GoogleAuthUnsecuredModeRefusedError(
            "google OAuth refused: secret store is unsecured and the active profile carries a real NIF",
            context={"profile": profile, "backend": "unsecured"},
            translated_message="adapters.google.oauth_flow.errors.unsecured_mode_refused",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.CREDENTIAL_STORE_SECURED,
                facts={"secret_store_secured": False, "tax_id_present": True},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )


def resolve_active_tax_id(profile_id: str) -> str:
    """Return the ``identity.tax_id`` value for the profile UUID.

    ``profile_id`` is the immutable profile identity returned by
    :func:`adapters.outbound.google.resolve_active_profile`.
    The resolver loads the profile bucket pointer through
    :func:`application.workflow.read_profile_bucket_by_id`, opens the
    canonical user-profile lifecycle service, and reads the tax-id fact used by
    :func:`adapters.outbound.google._oauth_flow.check_unsecured_mode_safety`.

    Returns:
        The stored ``identity.tax_id`` value, or an empty string when the
        profile record has no tax identifier.

    Raises:
        :exc:`adapters.outbound.google.GoogleAuthProfileUnboundError`:
            When the profile bucket manifest or canonical profile record cannot
            be resolved.
    """
    from ....application.user_profile import ProfileRecordRepository, record_to_path_values
    from ....application.workflow import read_profile_bucket_by_id

    pointer = read_profile_bucket_by_id(profile_id)
    if pointer is None:
        raise GoogleAuthProfileUnboundError(
            "google OAuth refused: active profile bucket manifest could not be resolved",
            context={"profile": profile_id, "reason": "profile_bucket_manifest_missing"},
            translated_message="adapters.google.oauth_flow.errors.profile_state_unresolved",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.PROFILE_IDENTITY_RESOLVED,
                facts={"profile_bucket_present": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        )
    try:
        record = ProfileRecordRepository.for_current_session(pointer.bucket_id).load(profile_id)
    except ProfileNotFoundError as exc:
        raise GoogleAuthProfileUnboundError(
            "google OAuth refused: active profile record could not be resolved",
            context={"profile": profile_id, "bucket_id": pointer.bucket_id, "reason": "profile_record_missing"},
            translated_message="adapters.google.oauth_flow.errors.profile_state_unresolved",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.PROFILE_IDENTITY_RESOLVED,
                facts={"profile_record_present": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        ) from exc
    return record_to_path_values(record).get("identity.tax_id") or ""


def credentials_to_records(
    *,
    refresh_token: str,
    token_uri: str,
    account_email: str,
    granted_scopes: tuple[str, ...],
    issued_at: datetime,
) -> tuple[OAuthToken, OAuthMetadata]:
    """Map OAuth credential fields into persisted Google session records.

    The consent screen must grant every scope in
    :data:`adapters.outbound.google.REQUIRED_SCOPES`. The returned
    :class:`adapters.outbound.google.OAuthToken` carries the refresh
    credential and the returned
    :class:`adapters.outbound.google.OAuthMetadata` carries the linked
    Google account, granted scope tuple, and issuance timestamps used by the
    session store.

    Args:
        refresh_token: The refresh token returned by the consent screen.
        token_uri: The token endpoint URL mirrored from
            :class:`adapters.outbound.google.OAuthClient`.
        account_email: The Google account that completed the consent.
        granted_scopes: Scopes the consent screen actually granted.
        issued_at: Timestamp the credential was first issued.

    Returns:
        A 2-tuple of (:class:`adapters.outbound.google.OAuthToken`,
        :class:`adapters.outbound.google.OAuthMetadata`) ready for
        :class:`adapters.persistence.storage.SecureObjectRepository`
        persistence through :mod:`adapters.outbound.google._session_store`.
        Both records validate strict pydantic invariants; metadata refuses
        granted-scope tuples missing any
        :data:`adapters.outbound.google.REQUIRED_SCOPES` member.

    Raises:
        :exc:`adapters.outbound.google.GoogleAuthScopeInsufficientError`:
            When ``granted_scopes`` omits any required scope. Re-raised
            separately from the pydantic ``ValidationError`` so the CLI can
            surface a concrete remediation hint.
    """
    missing = tuple(scope for scope in REQUIRED_SCOPES if scope not in granted_scopes)
    if missing:
        raise GoogleAuthScopeInsufficientError(
            f"consent screen returned without granting required scopes: {missing!r}",
            context={"missing_scopes": list(missing), "account_email": account_email},
            translated_message="adapters.google.oauth_flow.errors.scope_missing",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.REQUIRED_SCOPES_GRANTED,
                facts={"required_scopes_granted": False, "missing_scope_count": len(missing)},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
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
    :func:`adapters.outbound.google._oauth_flow.resolve_active_tax_id`,
    applies
    :func:`adapters.outbound.google._oauth_flow.check_unsecured_mode_safety`,
    requires
    :func:`adapters.outbound.google._oauth_flow.require_interactive_terminal`,
    then maps the resulting credential fields through
    :func:`adapters.outbound.google._oauth_flow.credentials_to_records`.

    Args:
        client: Operator-imported
            :class:`adapters.outbound.google.OAuthClient` metadata.
        profile: Active profile UUID resolved by
            :func:`adapters.outbound.google.resolve_active_profile`.

    Returns:
        A 2-tuple of (:class:`adapters.outbound.google.OAuthToken`,
        :class:`adapters.outbound.google.OAuthMetadata`) ready for
        persistence.

    Raises:
        :exc:`adapters.outbound.google.GoogleAuthError`: Any
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
    :exc:`adapters.outbound.google.GoogleAuthNetworkError` rather than
    an opaque ``ImportError``.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GoogleAuthNetworkError(
            f"google-auth-oauthlib not importable: {exc}",
            translated_message="adapters.google.oauth_flow.errors.oauthlib_not_importable",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.OAUTHLIB_AVAILABLE,
                facts={"oauthlib_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
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
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.OAUTH_CLIENT_CONFIG_VALID,
                facts={"oauth_client_config_valid": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc

    try:
        credentials = flow.run_local_server(port=0, timeout_seconds=_CONSENT_WAIT_TIMEOUT_SECONDS)
    except OSError as exc:
        raise GoogleAuthLoopbackBindError(
            f"loopback receiver failed to bind: {exc}",
            translated_message="adapters.google.oauth_flow.errors.loopback_bind_failed",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.LOOPBACK_RECEIVER_BOUND,
                facts={"loopback_receiver_bound": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
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
            translated_message="adapters.google.oauth_flow.errors.browser_launcher_refused",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.BROWSER_LAUNCHER_AVAILABLE,
                facts={"browser_launcher_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc
    if "transport" in message or "connect" in message or "network" in message:
        raise GoogleAuthNetworkError(
            f"OAuth endpoint unreachable: {exc}",
            translated_message="adapters.google.oauth_flow.errors.endpoint_unreachable",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.OAUTH_ENDPOINT_REACHABLE,
                facts={"oauth_endpoint_reachable": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc
    raise GoogleAuthNetworkError(
        f"OAuth local server flow failed: {exc}",
        context={"error_type": type(exc).__name__},
        translated_message="adapters.google.oauth_flow.errors.endpoint_unreachable",
        precondition_verdict=google_auth_no_action_verdict(
            condition=GoogleAuthPreconditionCondition.OAUTH_FLOW_COMPLETED,
            facts={"oauth_flow_completed": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.SAFETY,
        ),
    ) from exc


def _decode_email_from_id_token(credentials: object, *, audience: str) -> str:
    """Verify the ID token and return the ``email`` claim.

    Follows Google's OpenID Connect verification guidance:
    https://developers.google.com/identity/openid-connect/openid-connect#validatinganidtoken

    Verification requires the audience (our OAuth client_id) to match
    the token's ``aud`` claim.
    :data:`adapters.outbound.google.REQUIRED_SCOPES` must include the
    ``openid`` + ``userinfo.email`` pair for Google to include the ``email``
    claim in the ID token.

    Args:
        credentials: Google credentials object carrying ``id_token`` and ``scopes``.
        audience: OAuth client ID used as the expected ``aud`` claim.

    Returns:
        The verified email address extracted from the ID token payload.

    Raises:
        :exc:`adapters.outbound.google.GoogleAuthScopeInsufficientError`:
            When the credential carries no ``id_token`` or the verified payload
            has no ``email`` claim.
        :exc:`adapters.outbound.google.GoogleAuthNetworkError`: When
            ``google.oauth2.id_token`` is not importable or the verification
            HTTP fetch fails.
    """
    id_token_jwt = getattr(credentials, "id_token", None)
    if id_token_jwt is None:
        raise GoogleAuthScopeInsufficientError(
            "Google did not return an id_token; the OAuth consent did not include the openid+email scopes",
            context={"audience": audience},
            translated_message="adapters.google.oauth_flow.errors.id_token_missing",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_PRESENT,
                facts={"id_token_present": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    try:
        from google.auth.transport import requests as auth_requests
        from google.oauth2 import id_token as id_token_module
    except ImportError as exc:
        raise GoogleAuthNetworkError(
            f"google-auth id_token module not importable: {exc}",
            translated_message="adapters.google.oauth_flow.errors.id_token_module_not_importable",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_VERIFIER_AVAILABLE,
                facts={"id_token_verifier_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc
    try:
        payload = id_token_module.verify_oauth2_token(id_token_jwt, auth_requests.Request(), audience)
    except ValueError as exc:
        raise GoogleAuthNetworkError(
            f"id_token verification failed: {exc}",
            context={"audience": audience},
            translated_message="adapters.google.oauth_flow.errors.id_token_verification_failed",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_VERIFIED,
                facts={"id_token_verified": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc
    email = str(payload.get("email", ""))
    if not email:
        raise GoogleAuthScopeInsufficientError(
            "id_token verified but carries no `email` claim",
            context={"audience": audience},
            translated_message="adapters.google.oauth_flow.errors.email_claim_missing",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.IDENTITY_EMAIL_PRESENT,
                facts={"id_token_email_present": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return email


__all__ = [
    "check_unsecured_mode_safety",
    "credentials_to_records",
    "require_interactive_terminal",
    "resolve_active_tax_id",
    "run_login_flow",
]
