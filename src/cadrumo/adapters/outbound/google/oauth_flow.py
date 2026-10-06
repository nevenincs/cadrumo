"""Google OAuth Desktop login flow for per-profile Google sessions.

Runs this installation's :class:`core.config_google_client.OAuthClient`
through Google's loopback IP + PKCE Desktop flow using
a bounded, single-use loopback receiver.
The operating system picks an ephemeral loopback port and opens the
consent screen in the operator's default browser.

Two policy gates fire before any network IO happens:

1. The caller must pass a profile identity resolved by
   :func:`adapters.outbound.google.active_profile.resolve_active_profile`.
2. :func:`adapters.outbound.google.oauth_flow.require_resolvable_profile_record`
   refuses a profile whose canonical record session cannot be opened.

See Also:
    :func:`adapters.outbound.google.oauth_flow.run_login_flow` executes the login
    path, :func:`adapters.outbound.google.oauth_flow.credentials_to_records`
    produces :class:`adapters.outbound.google.records.OAuthToken` and
    :class:`adapters.outbound.google.records.OAuthMetadata`, and
    :data:`adapters.outbound.google.records.REQUIRED_SCOPES` defines the consent
    surface the Google account must grant.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from datetime import datetime
from typing import TYPE_CHECKING, NoReturn, Protocol, cast

from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationHandoff,
)
from ....core.config_google_client import OAuthClient
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.time.clock import now
from ....core.tty import stdin_is_tty
from ....domain.user_profile.errors import ProfileNotFoundError
from .errors import (
    GoogleAuthBrowserOpenError,
    GoogleAuthLoopbackBindError,
    GoogleAuthNetworkError,
    GoogleAuthNonInteractiveError,
    GoogleAuthPreconditionCondition,
    GoogleAuthProfileUnboundError,
    GoogleAuthScopeInsufficientError,
    GoogleAuthSignInRequiredError,
    GoogleAuthValidationError,
    google_auth_no_action_verdict,
)
from .oauth_callback import LOOPBACK_HOST, OAuthCallbackBindError, OAuthConsentDeclinedError, receive_authorization_code
from .records import REQUIRED_SCOPES, OAuthMetadata, OAuthToken

if TYPE_CHECKING:
    from google_auth_oauthlib.flow import OAuthCredentials

    from ....domain.calculations.registry.authority import PinnedAuthorityOperation

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
    :func:`adapters.outbound.google.oauth_flow.run_login_flow` calls the local receiver.

    Raises:
        :exc:`adapters.outbound.google.errors.GoogleAuthNonInteractiveError`:
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


def require_resolvable_profile_record(profile_id: str, *, operation: PinnedAuthorityOperation | None = None) -> None:
    """Refuse the consent flow when the active profile cannot be resolved.

    ``profile_id`` is the immutable profile identity returned by
    :func:`adapters.outbound.google.active_profile.resolve_active_profile`. The guard reads the
    profile bucket pointer through
    :func:`application.workflow.profile_bucket_scan.read_profile_bucket_by_id` and opens the
    canonical user-profile record through its lifecycle service, so a profile
    that is committed but has no live record session is refused BEFORE any
    network IO rather than midway through consent.

    Nothing is read out of the record: existence is the whole precondition.

    Args:
        profile_id: Exact active profile identity whose record must resolve.
        operation: Retained authority pin; ordinary callers use the bundled pin.

    Raises:
        :exc:`adapters.outbound.google.errors.GoogleAuthProfileUnboundError`:
            When the profile bucket pointer or the canonical profile-record
            session cannot be resolved.
    """
    from ....application.user_profile.profile_record_repository import ProfileRecordRepository
    from ....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
    from ....domain.calculations.registry.authority import bundled_indexed_authority

    pointer = read_profile_bucket_by_id(profile_id)
    if pointer is None:
        raise GoogleAuthProfileUnboundError(
            "google OAuth refused: active profile bucket pointer could not be resolved",
            context={"profile": profile_id, "reason": "profile_bucket_pointer_missing"},
            translated_message="adapters.google.oauth_flow.errors.profile_state_unresolved",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.PROFILE_IDENTITY_RESOLVED,
                facts={"profile_bucket_present": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        )
    authority_scope = nullcontext(operation) if operation is not None else bundled_indexed_authority().operation()
    with authority_scope as active_operation:
        try:
            ProfileRecordRepository.for_current_session(
                pointer.bucket_id,
                profile_decode_context=active_operation.profile_decode_context(),
            ).load(profile_id)
        except ProfileNotFoundError as exc:
            raise GoogleAuthProfileUnboundError(
                "google OAuth refused: active profile record session is unavailable",
                context={
                    "profile": profile_id,
                    "bucket_id": pointer.bucket_id,
                    "reason": "profile_record_session_unavailable",
                },
                translated_message="adapters.google.oauth_flow.errors.profile_state_unresolved",
                precondition_verdict=google_auth_no_action_verdict(
                    condition=GoogleAuthPreconditionCondition.PROFILE_RECORD_SESSION_AVAILABLE,
                    facts={"profile_record_session_available": False},
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            ) from exc


def credentials_to_records(
    *,
    refresh_token: str,
    client_id: str,
    token_uri: str,
    account_email: str,
    granted_scopes: tuple[str, ...],
    issued_at: datetime,
) -> tuple[OAuthToken, OAuthMetadata]:
    """Map OAuth credential fields into persisted Google session records.

    The consent screen must grant every scope in
    :data:`adapters.outbound.google.records.REQUIRED_SCOPES`. The returned
    :class:`adapters.outbound.google.records.OAuthToken` carries the refresh
    credential and the returned
    :class:`adapters.outbound.google.records.OAuthMetadata` carries the linked
    Google account, granted scope tuple, and issuance timestamp used by the
    session store.

    Args:
        refresh_token: The refresh token returned by the consent screen.
        client_id: The client the consent was granted to, bound into the token.
        token_uri: The token endpoint URL mirrored from
            :class:`core.config_google_client.OAuthClient`.
        account_email: The Google account that completed the consent.
        granted_scopes: Scopes the consent screen actually granted.
        issued_at: Timestamp the credential was first issued.

    Returns:
        A 2-tuple of (:class:`adapters.outbound.google.records.OAuthToken`,
        :class:`adapters.outbound.google.records.OAuthMetadata`) ready for
        :class:`adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
        persistence through :mod:`adapters.outbound.google.session_store`.
        Both records validate strict pydantic invariants; metadata refuses
        granted-scope tuples missing any
        :data:`adapters.outbound.google.records.REQUIRED_SCOPES` member.

    Raises:
        :exc:`adapters.outbound.google.errors.GoogleAuthScopeInsufficientError`:
            When ``granted_scopes`` omits any required scope. Re-raised
            separately from the pydantic ``ValidationError`` so the CLI can
            surface a concrete remediation hint.
    """
    missing = tuple(scope for scope in REQUIRED_SCOPES if scope not in granted_scopes)
    if missing:
        from .errors import GoogleScopeFailure

        raise GoogleAuthScopeInsufficientError(
            f"consent screen returned without granting required scopes: {missing!r}",
            context={"missing_scopes": list(missing), "account_email": account_email},
            translated_message="adapters.google.oauth_flow.errors.scope_missing",
            scope_failure=GoogleScopeFailure(missing_scopes=missing, account_email=account_email),
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.REQUIRED_SCOPES_GRANTED,
                facts={"required_scopes_granted": False, "missing_scope_count": len(missing)},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    token = OAuthToken(refresh_token=refresh_token, client_id=client_id, token_uri=token_uri)
    metadata = OAuthMetadata(
        account_email=account_email,
        granted_scopes=tuple(granted_scopes),
        issued_at=issued_at,
    )
    return token, metadata


def run_login_flow(
    client: OAuthClient,
    profile: str,
    *,
    operation: PinnedAuthorityOperation | None = None,
    terminal_admission: Callable[[], None] | None = None,
    before_handoff: GoogleConfigurationHandoff | None = None,
    acknowledged: GoogleConfigurationAcknowledgement | None = None,
) -> tuple[OAuthToken, OAuthMetadata]:
    """Execute the loopback-IP + PKCE OAuth Desktop flow.

    Uses a bounded, single-use loopback receiver and the real OAuth library
    against ``accounts.google.com``. The flow checks profile state with
    :func:`adapters.outbound.google.oauth_flow.require_resolvable_profile_record`,
    requires
    :func:`adapters.outbound.google.oauth_flow.require_interactive_terminal`,
    then maps the resulting credential fields through
    :func:`adapters.outbound.google.oauth_flow.credentials_to_records`.

    Args:
        client: This installation's
            :class:`core.config_google_client.OAuthClient` metadata.
        profile: Active profile UUID resolved by
            :func:`adapters.outbound.google.active_profile.resolve_active_profile`.
        operation: Retained authority pin for canonical profile-record admission.
        terminal_admission: Consumed exact human interaction proof, or the ordinary TTY guard.
        before_handoff: Renew authority immediately before each remote boundary.
        acknowledged: Record completion of each admitted remote boundary.

    Returns:
        A 2-tuple of (:class:`adapters.outbound.google.records.OAuthToken`,
        :class:`adapters.outbound.google.records.OAuthMetadata`) ready for
        persistence.

    Raises:
        :exc:`adapters.outbound.google.errors.GoogleAuthError`: Any
            typed OAuth refusal with concrete remediation context.
    """
    if operation is None:
        require_resolvable_profile_record(profile)
    else:
        require_resolvable_profile_record(profile, operation=operation)
    # Gate the blocking loopback consent receiver: refuse fast in a
    # non-interactive shell rather than hang forever waiting for a browser
    # redirect no operator can complete. Placed after the profile gate so
    # its more-specific refusal takes precedence, and immediately
    # before the only call that would block.
    (terminal_admission or require_interactive_terminal)()
    if before_handoff is None and acknowledged is None:
        refresh_token, token_uri, account_email, granted_scopes = _run_local_server(client)
    else:
        refresh_token, token_uri, account_email, granted_scopes = _run_local_server(
            client, before_handoff=before_handoff, acknowledged=acknowledged
        )
    return credentials_to_records(
        refresh_token=refresh_token,
        client_id=client.client_id,
        token_uri=token_uri,
        account_email=account_email,
        granted_scopes=granted_scopes,
        issued_at=now(),
    )


def _run_local_server(
    client: OAuthClient,
    *,
    before_handoff: GoogleConfigurationHandoff | None = None,
    acknowledged: GoogleConfigurationAcknowledgement | None = None,
) -> tuple[str, str, str, tuple[str, ...]]:
    """Loopback-IP + PKCE OAuth Desktop flow runner.

    Imports ``google_auth_oauthlib`` lazily so the failure mode of a
    missing transitive dependency surfaces as a typed
    :exc:`adapters.outbound.google.errors.GoogleAuthNetworkError` rather than
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

    client_config = _oauth_loopback_client_config(client)

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    try:
        flow = InstalledAppFlow.from_client_config(
            client_config, scopes=list(REQUIRED_SCOPES), state=state, autogenerate_code_verifier=True
        )
    except ValueError:
        raise GoogleAuthNetworkError(
            "OAuth client config refused",
            translated_message="adapters.google.oauth_flow.errors.client_config_refused",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.OAUTH_CLIENT_CONFIG_VALID,
                facts={"oauth_client_config_valid": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None

    def authorization_url(redirect_uri: str) -> str:
        flow.redirect_uri = redirect_uri
        url, _state = flow.authorization_url(nonce=nonce, code_challenge_method="S256")
        return url

    if before_handoff is not None:
        before_handoff("oauth.browser-consent")
    try:
        code = receive_authorization_code(authorization_url, state=state, timeout_seconds=_CONSENT_WAIT_TIMEOUT_SECONDS)
        if before_handoff is not None:
            before_handoff("oauth.token-exchange", writes=True)
        # State is checked by the single-use receiver before passing the code.
        # Flow adds the fresh verifier to this bounded HTTPS token exchange.
        flow.fetch_token(code=code, timeout=30)
        if acknowledged is not None:
            acknowledged("oauth.token-exchange", writes=True)
    except OAuthConsentDeclinedError:
        raise _consent_declined_refusal() from None
    except OAuthCallbackBindError:
        raise GoogleAuthLoopbackBindError(
            "loopback receiver failed to bind",
            translated_message="adapters.google.oauth_flow.errors.loopback_bind_failed",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.LOOPBACK_RECEIVER_BOUND,
                facts={"loopback_receiver_bound": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    except (ProfileAccessRefusedError, GoogleAuthSignInRequiredError):
        raise
    except Exception as exc:
        _raise_local_server_error(exc)

    if acknowledged is not None:
        acknowledged("oauth.browser-consent")
    return _oauth_loopback_records(
        flow.credentials, client, before_handoff=before_handoff, acknowledged=acknowledged, expected_nonce=nonce
    )


def _consent_declined_refusal() -> GoogleAuthSignInRequiredError:
    """Build the refusal for a consent that was declined before anything was exchanged."""
    return GoogleAuthSignInRequiredError(
        "the Google consent was declined",
        translated_message="adapters.google.oauth_flow.errors.consent_declined",
        precondition_verdict=google_auth_no_action_verdict(
            condition=GoogleAuthPreconditionCondition.CONSENT_GRANTED,
            facts={"consent_granted": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def _raise_local_server_error(exc: Exception) -> NoReturn:
    """Translate upstream local-server OAuth failures into the Google auth hierarchy."""
    message = str(exc).lower()
    if "browser" in message or "webbrowser" in message:
        raise GoogleAuthBrowserOpenError(
            "OS browser launcher refused",
            translated_message="adapters.google.oauth_flow.errors.browser_launcher_refused",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.BROWSER_LAUNCHER_AVAILABLE,
                facts={"browser_launcher_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    if "transport" in message or "connect" in message or "network" in message:
        raise GoogleAuthNetworkError(
            "OAuth endpoint unreachable",
            translated_message="adapters.google.oauth_flow.errors.endpoint_unreachable",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.OAUTH_ENDPOINT_REACHABLE,
                facts={"oauth_endpoint_reachable": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    raise GoogleAuthNetworkError(
        "OAuth local server flow failed",
        context={"error_type": type(exc).__name__},
        translated_message="adapters.google.oauth_flow.errors.endpoint_unreachable",
        precondition_verdict=google_auth_no_action_verdict(
            condition=GoogleAuthPreconditionCondition.OAUTH_FLOW_COMPLETED,
            facts={"oauth_flow_completed": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.SAFETY,
        ),
    ) from None


class _IdTokenVerifier(Protocol):
    """The `google.oauth2.id_token` surface this adapter calls.

    The module ships `py.typed` but leaves `verify_oauth2_token` unannotated,
    so calling it through the module object yields an unknown payload. The
    verified claim set is a JSON object; callers narrow each claim they read.
    """

    def verify_oauth2_token(
        self,
        id_token: str | bytes,
        request: object,
        audience: str,
    ) -> Mapping[str, object]: ...


def _decode_email_from_id_token(
    credentials: object,
    *,
    audience: str,
    before_handoff: GoogleConfigurationHandoff | None = None,
    acknowledged: GoogleConfigurationAcknowledgement | None = None,
    expected_nonce: str,
) -> str:
    """Verify the ID token and return the ``email`` claim.

    Follows Google's OpenID Connect verification guidance:
    https://developers.google.com/identity/openid-connect/openid-connect#validatinganidtoken

    Verification requires the audience (our OAuth client_id) to match
    the token's ``aud`` claim.
    :data:`adapters.outbound.google.records.REQUIRED_SCOPES` must include the
    ``openid`` + ``userinfo.email`` pair for Google to include the ``email``
    claim in the ID token.

    Args:
        credentials: Google credentials object carrying ``id_token`` and ``scopes``.
        audience: OAuth client ID used as the expected ``aud`` claim.
        before_handoff: Recheck operation authority before each network handoff.
        acknowledged: Record a completed provider response.
        expected_nonce: Fresh nonce bound to this authorization request.

    Returns:
        The verified email address extracted from the ID token payload.

    Raises:
        :exc:`adapters.outbound.google.errors.GoogleAuthScopeInsufficientError`:
            When the credential carries no ``id_token`` or the verified payload
            has no ``email`` claim.
        :exc:`adapters.outbound.google.errors.GoogleAuthNetworkError`: When
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
        ) from None
    try:
        # CAST-RATIONALE-thirdparty: `verify_oauth2_token` is unannotated upstream.
        verifier = cast(_IdTokenVerifier, id_token_module)
        if before_handoff is None and acknowledged is None:
            request = auth_requests.Request()
        else:
            from .google_configuration_admission import admitted_google_auth_request

            request = admitted_google_auth_request(
                before_handoff=before_handoff, acknowledged=acknowledged, action="oauth.identity-verification"
            )
        payload = verifier.verify_oauth2_token(id_token_jwt, request, audience)
    except ProfileAccessRefusedError:
        raise
    except Exception:
        raise GoogleAuthNetworkError(
            "id_token verification failed",
            context={"audience": audience},
            translated_message="adapters.google.oauth_flow.errors.id_token_verification_failed",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_VERIFIED,
                facts={"id_token_verified": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    email = payload.get("email")
    subject = payload.get("sub")
    if (
        not isinstance(email, str)
        or not email.strip()
        or payload.get("email_verified") is not True
        or not isinstance(subject, str)
        or not subject.strip()
        or (payload.get("nonce") != expected_nonce)
        or (payload.get("azp") is not None and payload.get("azp") != audience)
    ):
        raise GoogleAuthValidationError(
            "id_token carries incomplete or uncorrelated identity claims",
            context={"audience": audience},
            translated_message="errors.refused.refused_google_validation",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_VERIFIED,
                facts={"id_token_verified": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return email


__all__ = [
    "credentials_to_records",
    "require_interactive_terminal",
    "require_resolvable_profile_record",
    "run_login_flow",
]


def _oauth_loopback_client_config(client: OAuthClient) -> dict[str, dict[str, object]]:
    """Build the unchanged desktop client configuration before consent begins."""
    return {
        "installed": {
            "client_id": client.client_id,
            "client_secret": client.client_secret,
            "project_id": client.project_id,
            "auth_uri": client.auth_uri,
            "token_uri": client.token_uri,
            "auth_provider_x509_cert_url": client.auth_provider_x509_cert_url,
            "redirect_uris": list(client.redirect_uris) or [f"http://{LOOPBACK_HOST}"],
        }
    }


def _oauth_loopback_records(
    credentials: OAuthCredentials,
    client: OAuthClient,
    *,
    before_handoff: GoogleConfigurationHandoff | None,
    acknowledged: GoogleConfigurationAcknowledgement | None,
    expected_nonce: str,
) -> tuple[str, str, str, tuple[str, ...]]:
    """Verify the admitted identity and retain the refresh and scope facts in evaluation order."""
    refresh_token = credentials.refresh_token
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        # Without a refresh token the sign-in would work until the access token
        # lapses and then fail on every later command, so nothing is stored.
        raise GoogleAuthValidationError(
            "Google completed the consent without issuing a refresh token",
            translated_message="adapters.google.oauth_flow.errors.refresh_token_missing",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.REFRESH_CREDENTIAL_ISSUED,
                facts={"refresh_token_issued": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    granted_scopes = tuple(credentials.granted_scopes or ())
    if set(granted_scopes) != set(REQUIRED_SCOPES):
        raise GoogleAuthScopeInsufficientError(
            "Google did not confirm the exact required scope grant",
            translated_message="errors.auth.auth_google_scope_insufficient",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.REQUIRED_SCOPES_GRANTED,
                facts={"required_scopes_granted": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return (
        refresh_token,
        client.token_uri,
        _decode_email_from_id_token(
            credentials,
            audience=client.client_id,
            before_handoff=before_handoff,
            acknowledged=acknowledged,
            expected_nonce=expected_nonce,
        ),
        granted_scopes,
    )
