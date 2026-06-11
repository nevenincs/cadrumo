"""Shared exception types for AEAT authentication providers."""

from __future__ import annotations

from .....core.errors import AeatError


class AuthError(AeatError):
    """Base class for every outbound AEAT authentication domain error."""


class AuthConfigurationError(AuthError):
    """Raised when required authentication settings are missing or malformed."""


class AuthValidationError(AuthError, ValueError):
    """Raised when authentication parameters or field values fail domain validation.

    This error inherits from both :class:`AuthError` and :class:`ValueError`,
    ensuring compatibility with Pydantic's validator contract while
    remaining catchable under the package's unified error hierarchy.
    """



class AeatLoginAssertionError(AuthError):
    """Raised when a post-auth verification attempt cannot be produced.

    This exception fires when the assertion cannot even be built — for
    example a Playwright context is missing a required marker,
    the authenticator was never authenticated, or a structural
    precondition failed before the navigation could complete.
    """


class AeatSessionExpiredError(AuthError):
    """Raised when an authenticated AEAT session is no longer usable.

    Conditions feeding this error include:
    1. An idle deadline has elapsed.
    2. A reauthentication attempt fails.
    3. An HTTP 401 / 403 surfaced by a downstream live-read call site.
    """
