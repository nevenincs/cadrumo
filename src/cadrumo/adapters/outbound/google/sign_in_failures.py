"""The closed failure category of every Google sign-in failure.

A Google sign-in is the profile's own act, not a setup item, but its failures
are worded with the same closed categories as setup: a refused or failed
sign-in maps to exactly one through :func:`google_failure_category`, by
exception type and refusal condition and never by message text.
"""

from __future__ import annotations

import socket
import ssl
from collections.abc import Mapping
from typing import Final, NamedTuple

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.google_auth import GoogleAuthError, GoogleAuthPreconditionCondition

from ..storage import errors as storage_errors

_CONDITION_CATEGORIES: Final[Mapping[GoogleAuthPreconditionCondition, DependencyFailureCategory]] = {
    GoogleAuthPreconditionCondition.ACTIVE_PROFILE_RESOLVED: DependencyFailureCategory.UNEXPECTED,
    GoogleAuthPreconditionCondition.INTERACTIVE_TERMINAL_AVAILABLE: DependencyFailureCategory.NEEDS_SIGN_IN,
    GoogleAuthPreconditionCondition.PROFILE_IDENTITY_RESOLVED: DependencyFailureCategory.UNEXPECTED,
    GoogleAuthPreconditionCondition.PROFILE_RECORD_SESSION_AVAILABLE: DependencyFailureCategory.UNEXPECTED,
    GoogleAuthPreconditionCondition.REQUIRED_SCOPES_GRANTED: DependencyFailureCategory.NEEDS_SIGN_IN,
    GoogleAuthPreconditionCondition.CONSENT_GRANTED: DependencyFailureCategory.CANCELLED,
    GoogleAuthPreconditionCondition.REFRESH_CREDENTIAL_ISSUED: DependencyFailureCategory.NEEDS_SIGN_IN,
    GoogleAuthPreconditionCondition.SIGN_IN_CLIENT_BOUND: DependencyFailureCategory.NEEDS_SIGN_IN,
    GoogleAuthPreconditionCondition.GRANT_ACTIVE: DependencyFailureCategory.NEEDS_SIGN_IN,
    GoogleAuthPreconditionCondition.SIGN_IN_RECORD_READABLE: DependencyFailureCategory.NEEDS_SIGN_IN,
    GoogleAuthPreconditionCondition.OAUTHLIB_AVAILABLE: DependencyFailureCategory.NOT_IN_THIS_BUILD,
    GoogleAuthPreconditionCondition.CLIENT_METADATA_AVAILABLE: DependencyFailureCategory.NOT_IN_THIS_BUILD,
    GoogleAuthPreconditionCondition.OAUTH_CLIENT_CONFIG_VALID: DependencyFailureCategory.NOT_IN_THIS_BUILD,
    GoogleAuthPreconditionCondition.LOOPBACK_RECEIVER_BOUND: DependencyFailureCategory.UNEXPECTED,
    GoogleAuthPreconditionCondition.BROWSER_LAUNCHER_AVAILABLE: DependencyFailureCategory.UNEXPECTED,
    GoogleAuthPreconditionCondition.OAUTH_ENDPOINT_REACHABLE: DependencyFailureCategory.HOST_UNREACHABLE,
    GoogleAuthPreconditionCondition.OAUTH_FLOW_COMPLETED: DependencyFailureCategory.UNEXPECTED,
    GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_PRESENT: DependencyFailureCategory.NEEDS_SIGN_IN,
    GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_VERIFIER_AVAILABLE: DependencyFailureCategory.NOT_IN_THIS_BUILD,
    GoogleAuthPreconditionCondition.IDENTITY_ASSERTION_VERIFIED: DependencyFailureCategory.UNEXPECTED,
}
"""The category of every Google sign-in refusal condition; total over the closed condition set."""

# A Drive refusal on the profile's own folder is remedied by signing in again,
# which creates a fresh folder; the rest are not the person's to fix here.
_STORAGE_CATEGORIES: Final[Mapping[type[storage_errors.OutboundStorageError], DependencyFailureCategory]] = {
    storage_errors.OutboundStoragePermissionError: DependencyFailureCategory.NEEDS_SIGN_IN,
    storage_errors.OutboundStorageNotFoundError: DependencyFailureCategory.NEEDS_SIGN_IN,
    storage_errors.OutboundStorageConflictError: DependencyFailureCategory.NEEDS_SIGN_IN,
    storage_errors.OutboundStorageValidationError: DependencyFailureCategory.NEEDS_SIGN_IN,
    storage_errors.OutboundStorageNetworkError: DependencyFailureCategory.HOST_UNREACHABLE,
}


def google_condition_category(condition_id: str) -> DependencyFailureCategory | None:
    """Return the category of a Google sign-in refusal condition id, or ``None`` for another id.

    A frontend that receives a refusal projection rather than the error reads
    its verdict's failed condition id through this mapping.
    """
    try:
        condition = GoogleAuthPreconditionCondition(condition_id)
    except ValueError:
        return None
    return _CONDITION_CATEGORIES[condition]


def google_failure_category(error: BaseException) -> DependencyFailureCategory:
    """Return the one closed category a Google failure falls into.

    The connection failure underneath, when there is one, is the most precise
    fact; then the Google refusal condition; then the Drive refusal type.
    Anything else is unexpected.
    """
    network = _network_category(error)
    if network is not None:
        return network
    if isinstance(error, GoogleAuthError):
        verdict = error.terminal_precondition_verdict
        if verdict is not None:
            category = google_condition_category(verdict.failed_condition_id)
            if category is not None:
                return category
        return DependencyFailureCategory.UNEXPECTED
    if isinstance(error, storage_errors.OutboundStorageError):
        return _STORAGE_CATEGORIES.get(type(error), DependencyFailureCategory.UNEXPECTED)
    return DependencyFailureCategory.UNEXPECTED


class _ConnectionFailureTypes(NamedTuple):
    """Native and optional requests-library error types in classification order."""

    proxy: tuple[type[BaseException], ...]
    secure: tuple[type[BaseException], ...]
    unreachable: tuple[type[BaseException], ...]


def _connection_failure_types() -> _ConnectionFailureTypes:
    """Load optional transport error classes while retaining native fallback categories."""
    try:
        from requests import exceptions as requests_errors
    except ImportError:
        requests_errors = None
    return _ConnectionFailureTypes(
        () if requests_errors is None else (requests_errors.ProxyError,),
        (ssl.SSLError,) if requests_errors is None else (ssl.SSLError, requests_errors.SSLError),
        (ConnectionError, TimeoutError)
        if requests_errors is None
        else (ConnectionError, TimeoutError, requests_errors.ConnectionError, requests_errors.Timeout),
    )


def _network_category(error: BaseException) -> DependencyFailureCategory | None:
    """Classify the first connection failure in ``error``'s cause chain, by type."""
    types = _connection_failure_types()
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, types.proxy):
            return DependencyFailureCategory.BLOCKED_BY_NETWORK
        if isinstance(current, types.secure):
            return DependencyFailureCategory.SECURE_CONNECTION_FAILED
        if isinstance(current, socket.gaierror):
            return DependencyFailureCategory.OFFLINE
        if isinstance(current, types.unreachable):
            return DependencyFailureCategory.HOST_UNREACHABLE
        current = current.__cause__ or current.__context__
    return None


__all__ = ["google_condition_category", "google_failure_category"]
