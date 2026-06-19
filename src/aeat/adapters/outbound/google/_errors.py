"""Typed exception hierarchy for the Google OAuth Desktop integration.

Every subclass binds to a stable `ErrorCode` declared in
`aeat.core.errors.registry._adapters` so the public CLI taxonomy stays
explicit and grep-stable. Constructors carry structured remediation
context (`context={...}`) so renderers can surface actionable guidance
without leaking the underlying secret material that the OAuth flow
handles.
"""

from __future__ import annotations

from ....core.errors import AeatError


class GoogleAuthError(AeatError):
    """Base class for every Google OAuth Desktop authentication failure."""


class GoogleAuthValidationError(GoogleAuthError):
    """Raised when input parameters fail validation."""


class GoogleAuthClientNotRegisteredError(GoogleAuthError):
    """Raised when no Cloud Console Desktop OAuth client is registered for the active profile."""


class GoogleAuthClientRevokedError(GoogleAuthError):
    """Raised when the operator (or Google) revoked the registered Desktop OAuth client."""


class GoogleAuthRevokedError(GoogleAuthError):
    """Raised when the refresh token was revoked (e.g. via myaccount.google.com).

    Maps to Google's `invalid_grant` response with `error_description="Token has been expired or revoked."`.
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
    """Raised on OAuth attempts under ``aeat_secret_store_backend=unsecured`` with a real NIF profile."""


class GoogleAuthKeychainLockedError(GoogleAuthError):
    """Raised when the OS keychain backing the secret store is locked or unreachable."""


class GoogleAuthProfileUnboundError(GoogleAuthError):
    """Raised when no active profile is bound on workflow state and no `--profile` override is given."""


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
    "GoogleAuthProfileUnboundError",
    "GoogleAuthRevokedError",
    "GoogleAuthScopeInsufficientError",
    "GoogleAuthUnsecuredModeRefusedError",
    "GoogleAuthValidationError",
]
