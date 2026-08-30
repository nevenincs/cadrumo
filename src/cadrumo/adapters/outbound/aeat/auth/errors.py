"""Shared exception taxonomy for outbound AEAT authentication.

Every class here inherits from :class:`~core.errors.CadrumoError`, so the
core error registry binds a stable :class:`~core.errors.ErrorCode` and
locale message key to the public auth failure surface. Certificate and Cl@ve
Móvil providers raise these errors with ``translated_message`` keys when a
provider precondition, verification probe, persisted-session check, or
configuration guard refuses to continue.

See Also:
    :mod:`adapters.outbound.aeat.auth` for the public auth surface,
    :class:`adapters.outbound.aeat.auth.AeatSession` for successful live
    sessions, and :class:`adapters.outbound.aeat.auth.AeatLoginAssertion`
    for verification outcomes that can be returned without raising.
"""

from __future__ import annotations

from .....core.errors.hierarchy import AuthError


class AuthConfigurationError(AuthError):
    """Raised when required authentication settings are missing or malformed.

    This covers provider selection and configuration refusals before browser or
    certificate work begins. Provider-specific subclasses such as
    :class:`adapters.outbound.aeat.auth.ClaveMovilConfigurationError` keep
    their own public identity while remaining catchable through this shared
    configuration arm.
    """


class AuthProviderCleanupError(AuthError):
    """Raised when an auth provider retains browser resources after close."""


class AuthValidationError(AuthError, ValueError):
    """Raised when authentication parameters or field values fail domain validation.

    This error inherits from both :class:`AuthError` and :class:`ValueError`,
    ensuring compatibility with Pydantic's validator contract while remaining
    catchable under the package's unified error hierarchy. Certificate health
    and field-validation helpers use this class when invalid values should
    behave like validation failures and still carry auth-domain error metadata.
    """


class AeatSessionExpiredError(AuthError):
    """Raised when an authenticated AEAT session is no longer usable.

    Conditions feeding this error include an
    :class:`adapters.outbound.aeat.auth.AeatSession` idle deadline that
    has elapsed, a failed single-shot reauthentication attempt, or an HTTP
    401/403 surfaced by a downstream live-read call site. The registered error
    code is retryable so operator flows can prompt for a fresh authentication
    attempt.
    """


__all__ = [
    "AeatSessionExpiredError",
    "AuthConfigurationError",
    "AuthProviderCleanupError",
    "AuthValidationError",
]
