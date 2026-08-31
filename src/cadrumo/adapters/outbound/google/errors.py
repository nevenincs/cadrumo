"""Typed exception hierarchy for the Google OAuth Desktop integration.

Every subclass is an :class:`core.errors.CadrumoError` with a stable
:class:`core.errors.ErrorCode` declared in the adapter error registry.
That keeps the public CLI taxonomy explicit while
:mod:`entrypoints.cli._config._google_errors` can map concrete
:class:`GoogleAuthError` subclasses to localised refusal text. Constructors
carry structured diagnostic context (``context={...}``) without leaking the
secret material handled by :mod:`adapters.outbound.google.oauth_flow`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from ....application.operator_actions._models import PreconditionVerdict
from ....application.operator_actions._preconditions import no_action_precondition_verdict
from ....core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome


class GoogleAuthPreconditionCondition(StrEnum):
    """Stable failed conditions observed by the Google authentication boundary."""

    ACTIVE_PROFILE_RESOLVED = "google.auth.active_profile.resolved"
    INTERACTIVE_TERMINAL_AVAILABLE = "google.auth.interactive_terminal.available"
    CREDENTIAL_STORE_SECURED = "google.auth.credential_store.secured"
    PROFILE_IDENTITY_RESOLVED = "google.auth.profile_identity.resolved"
    PROFILE_RECORD_SESSION_AVAILABLE = "google.auth.profile_record_session.available"
    REQUIRED_SCOPES_GRANTED = "google.auth.required_scopes.granted"
    OAUTHLIB_AVAILABLE = "google.auth.oauthlib.available"
    OAUTH_CLIENT_CONFIG_VALID = "google.auth.oauth_client_config.valid"
    LOOPBACK_RECEIVER_BOUND = "google.auth.loopback_receiver.bound"
    BROWSER_LAUNCHER_AVAILABLE = "google.auth.browser_launcher.available"
    OAUTH_ENDPOINT_REACHABLE = "google.auth.oauth_endpoint.reachable"
    OAUTH_FLOW_COMPLETED = "google.auth.oauth_flow.completed"
    IDENTITY_ASSERTION_PRESENT = "google.auth.identity_assertion.present"
    IDENTITY_ASSERTION_VERIFIER_AVAILABLE = "google.auth.identity_verifier.available"
    IDENTITY_ASSERTION_VERIFIED = "google.auth.identity_assertion.verified"
    IDENTITY_EMAIL_PRESENT = "google.auth.identity_email.present"
    ADC_CLIENT_AVAILABLE = "google.auth.adc_client.available"
    ADC_AVAILABLE = "google.auth.adc.available"
    IAM_CREDENTIAL_MINTED = "google.auth.iam_credential.minted"
    ADC_SOURCE_FRESH = "google.auth.adc_source.fresh"


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
    preserving the concrete :class:`core.errors.ErrorCode` on each leaf.
    """


class GoogleAuthValidationError(GoogleAuthError):
    """Raised when input parameters fail validation."""


class GoogleAuthClientNotRegisteredError(GoogleAuthError):
    """Raised when no Cloud Console Desktop OAuth client is registered for the active profile."""


class GoogleAuthClientRevokedError(GoogleAuthError):
    """Raised when the operator (or Google) revoked the registered Desktop OAuth client."""


class GoogleAuthRevokedError(GoogleAuthError):
    """Raised when the refresh token was revoked (e.g. via myaccount.google.com).

    Maps to Google's ``invalid_grant`` response with
    ``error_description="Token has been expired or revoked."``.
    """


class GoogleAuthExpiredError(GoogleAuthError):
    """Raised when a Testing-project refresh token has aged past Google's 7-day cap."""


class GoogleAuthScopeInsufficientError(GoogleAuthError):
    """Raised when the granted scope set does not include every scope required by the call site."""


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


class GoogleAuthUnsecuredModeRefusedError(GoogleAuthError):
    """Raised on OAuth attempts under ``cadrumo_secret_store_backend=unsecured`` with a real NIF profile."""


class GoogleAuthKeychainLockedError(GoogleAuthError):
    """Raised when the OS keychain backing the secret store is locked or unreachable."""


class GoogleAuthProfileUnboundError(GoogleAuthError):
    """Raised when Google auth cannot resolve the active AEAT profile.

    Emitted by :func:`adapters.outbound.google.active_profile.resolve_active_profile`
    and profile-loading guards in :mod:`adapters.outbound.google.oauth_flow`.
    """


__all__ = [
    "GoogleAuthBrowserOpenError",
    "GoogleAuthClientNotRegisteredError",
    "GoogleAuthClientRevokedError",
    "GoogleAuthError",
    "GoogleAuthExpiredError",
    "GoogleAuthKeychainLockedError",
    "GoogleAuthLoopbackBindError",
    "GoogleAuthNetworkError",
    "GoogleAuthNonInteractiveError",
    "GoogleAuthPreconditionCondition",
    "GoogleAuthProfileUnboundError",
    "GoogleAuthRevokedError",
    "GoogleAuthScopeInsufficientError",
    "GoogleAuthUnsecuredModeRefusedError",
    "GoogleAuthValidationError",
    "google_auth_no_action_verdict",
]
