"""Typed exception hierarchy for the Google OAuth Desktop integration.

Every subclass is an :class:`core.errors.hierarchy.CadrumoError` with a stable
:class:`core.errors.error_codes.ErrorCode` declared in the adapter error registry.
That keeps the public CLI taxonomy explicit while
:mod:`entrypoints.cli.config.google_errors` can map concrete
:class:`GoogleAuthError` subclasses to localised refusal text. Constructors
carry structured diagnostic context (``context={...}``) without leaking the
secret material handled by :mod:`adapters.outbound.google.oauth_flow`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ....application.operator_actions.models import PreconditionVerdict
from ....application.operator_actions.preconditions import no_action_precondition_verdict
from ....core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome


class GoogleAuthPreconditionCondition(StrEnum):
    """Stable failed conditions observed by the Google authentication boundary."""

    ACTIVE_PROFILE_RESOLVED = "google.auth.active_profile.resolved"
    INTERACTIVE_TERMINAL_AVAILABLE = "google.auth.interactive_terminal.available"
    PROFILE_IDENTITY_RESOLVED = "google.auth.profile_identity.resolved"
    PROFILE_RECORD_SESSION_AVAILABLE = "google.auth.profile_record_session.available"
    REQUIRED_SCOPES_GRANTED = "google.auth.required_scopes.granted"
    CONSENT_GRANTED = "google.auth.consent.granted"
    REFRESH_CREDENTIAL_ISSUED = "google.auth.refresh_credential.issued"
    SIGN_IN_CLIENT_BOUND = "google.auth.sign_in_client.bound"
    GRANT_ACTIVE = "google.auth.grant.active"
    SIGN_IN_RECORD_READABLE = "google.auth.sign_in_record.readable"
    OAUTHLIB_AVAILABLE = "google.auth.oauthlib.available"
    CLIENT_METADATA_AVAILABLE = "google.auth.client_metadata.available"
    OAUTH_CLIENT_CONFIG_VALID = "google.auth.oauth_client_config.valid"
    LOOPBACK_RECEIVER_BOUND = "google.auth.loopback_receiver.bound"
    BROWSER_LAUNCHER_AVAILABLE = "google.auth.browser_launcher.available"
    OAUTH_ENDPOINT_REACHABLE = "google.auth.oauth_endpoint.reachable"
    OAUTH_FLOW_COMPLETED = "google.auth.oauth_flow.completed"
    IDENTITY_ASSERTION_PRESENT = "google.auth.identity_assertion.present"
    IDENTITY_ASSERTION_VERIFIER_AVAILABLE = "google.auth.identity_verifier.available"
    IDENTITY_ASSERTION_VERIFIED = "google.auth.identity_assertion.verified"


def google_auth_no_action_verdict(
    *,
    condition: GoogleAuthPreconditionCondition,
    facts: Mapping[str, str | int | bool],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
):
    """Delegate a fact-only Google-auth refusal to the public verdict authority."""
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=provenance,
        outcome=outcome,
    )


class GoogleAuthError(TerminalPreconditionErrorMixin[PreconditionVerdict], CadrumoError):
    """Base class for every Google OAuth Desktop authentication failure.

    Catch this at CLI boundaries that need one Google-auth refusal arm while
    preserving the concrete :class:`core.errors.error_codes.ErrorCode` on each leaf.
    """


class GoogleAuthValidationError(GoogleAuthError):
    """Raised when input parameters fail validation."""


class GoogleAuthClientMetadataUnavailableError(GoogleAuthError):
    """Raised when this installation carries no usable Google OAuth Desktop client metadata."""


class GoogleAuthClientRevokedError(GoogleAuthError):
    """Raised when Google no longer accepts this installation's Desktop OAuth client."""


class GoogleAuthSignInRequiredError(GoogleAuthError):
    """Raised when a profile has no Google sign-in it can use.

    Covers a grant Google reports as revoked or expired, a stored token that
    does not belong to the client this installation signs in with, and a
    consent that was declined. The remedy is the same in every case: sign
    in again.
    """


@dataclass(frozen=True, slots=True)
class GoogleScopeFailure:
    """Canonical scope-check values, independent of generic diagnostic context."""

    missing_scopes: tuple[str, ...]
    account_email: str


class GoogleAuthScopeInsufficientError(GoogleAuthError):
    """Raised when the granted scope set does not include every required scope."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: PreconditionVerdict | None = None,
        scope_failure: GoogleScopeFailure | None = None,
    ) -> None:
        """Preserve ordinary defaults and optionally retain the canonical scope check."""
        super().__init__(
            message, context=context, translated_message=translated_message, precondition_verdict=precondition_verdict
        )
        self._scope_failure = scope_failure

    @property
    def scope_failure(self) -> GoogleScopeFailure | None:
        """Return immutable owning scope facts, never an unchecked context map."""
        return self._scope_failure


class GoogleAuthNetworkError(GoogleAuthError):
    """Raised when the OAuth or token endpoint is unreachable (DNS, TLS, timeout, refused)."""


class GoogleAuthLoopbackBindError(GoogleAuthError):
    """Raised when the loopback HTTP receiver cannot bind a local port."""


class GoogleAuthBrowserOpenError(GoogleAuthError):
    """Raised when the OS-default browser launcher fails to open the consent URL."""


class GoogleAuthNonInteractiveError(GoogleAuthError):
    """Raised when the interactive browser consent flow is attempted without a controlling terminal.

    The Desktop OAuth flow opens the consent screen in a browser and then
    blocks a loopback HTTP receiver until the operator completes consent.
    With no controlling TTY (a piped, redirected, or detached invocation)
    no operator can complete the flow, so the receiver would block forever.
    This refusal fails fast instead, naming the interactive-terminal
    prerequisite.
    """


class GoogleAuthKeychainLockedError(GoogleAuthError):
    """Raised when the OS keychain backing the secret store is locked or unreachable."""


class GoogleAuthProfileUnboundError(GoogleAuthError):
    """Raised when Google auth cannot resolve the active AEAT profile.

    Emitted by :func:`adapters.outbound.google.active_profile.resolve_active_profile`
    and profile-loading guards in :mod:`adapters.outbound.google.oauth_flow`.
    """


__all__ = [
    "GoogleAuthBrowserOpenError",
    "GoogleAuthClientMetadataUnavailableError",
    "GoogleAuthClientRevokedError",
    "GoogleAuthError",
    "GoogleAuthKeychainLockedError",
    "GoogleAuthLoopbackBindError",
    "GoogleAuthNetworkError",
    "GoogleAuthNonInteractiveError",
    "GoogleAuthPreconditionCondition",
    "GoogleAuthProfileUnboundError",
    "GoogleAuthScopeInsufficientError",
    "GoogleAuthSignInRequiredError",
    "GoogleAuthValidationError",
    "GoogleScopeFailure",
    "google_auth_no_action_verdict",
]
