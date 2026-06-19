"""Shared refusal rendering for ``aeat config google`` commands."""

from __future__ import annotations

from ....adapters.outbound.google import GoogleAuthError
from ....adapters.outbound.storage import OutboundStorageError
from ....core.i18n import tr
from .._errors import CliRefusedBoundaryError

# `aeat config google ...` commands catch the broad GoogleAuthError base
# (and OutboundStorageError on Drive paths). `str(exc)` of either is the
# adapter's English message, so wrapping it straight into a refusal leaks
# English into every locale. Map the concrete exception type to a
# `cli.config.google.errors.*` key so the operator-facing refusal frame renders
# in the active output language.
_GOOGLE_ERROR_KEY_SUFFIX: dict[str, str] = {
    "GoogleAuthValidationError": "validation",
    "GoogleAuthClientNotRegisteredError": "client_not_registered",
    "GoogleAuthClientRevokedError": "client_revoked",
    "GoogleAuthRevokedError": "token_revoked",
    "GoogleAuthExpiredError": "token_expired",
    "GoogleAuthScopeInsufficientError": "scope_insufficient",
    "GoogleAuthNetworkError": "network",
    "GoogleAuthLoopbackBindError": "loopback_bind",
    "GoogleAuthBrowserOpenError": "browser_open",
    "GoogleAuthNonInteractiveError": "non_interactive",
    "GoogleAuthUnsecuredModeRefusedError": "unsecured_mode",
    "GoogleAuthKeychainLockedError": "keychain_locked",
    "GoogleAuthProfileUnboundError": "profile_unbound",
    "OutboundStorageError": "storage",
}


def _refusal_detail(exc: GoogleAuthError | OutboundStorageError) -> str:
    """Return the locale-rendered ``{detail}`` text for a wrapped failure."""
    translated_message = getattr(exc, "translated_message", None)
    if translated_message is not None:
        context = getattr(exc, "context", None) or {}
        return tr(translated_message, **context)
    return str(exc)


def _google_refusal(exc: GoogleAuthError | OutboundStorageError) -> CliRefusedBoundaryError:
    """Wrap a Google adapter failure in a locale-rendered CLI refusal."""
    suffix = _GOOGLE_ERROR_KEY_SUFFIX.get(type(exc).__name__, "auth_failed")
    return CliRefusedBoundaryError(
        translated_message=f"cli.config.google.errors.{suffix}",
        context={"detail": _refusal_detail(exc)},
    )


__all__ = ["_google_refusal"]
