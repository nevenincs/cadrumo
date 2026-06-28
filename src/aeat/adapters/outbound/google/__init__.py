"""Public re-exports for Google outbound adapter primitives.

This package boundary exposes OAuth records and scope constants from
:mod:`aeat.adapters.outbound.google._records`, the Google auth error taxonomy
from :mod:`aeat.adapters.outbound.google._errors`, and scoped document-link
helpers from :mod:`aeat.adapters.outbound.google._document_link_resolver`.
Google Sheets remains a one-way export mirror here, never an authority.

Major declarations:

* :class:`OAuthClient`, :class:`OAuthToken`, and :class:`OAuthMetadata` —
  the typed OAuth credential records.
* :class:`DriveAppProperties` — the typed Drive ``appProperties`` payload.
* :data:`REQUIRED_SCOPES`, with :data:`DRIVE_FILE_SCOPE` and
  :data:`SHEETS_SCOPE` — the requested OAuth scopes.
* :func:`parse_drive_file_id` and :func:`resolve_document_link` — the
  minimal-scope Drive document-link helpers.
* :class:`GoogleAuthError` and its subclasses — the Google auth failure
  taxonomy.
"""

from ._document_link_resolver import parse_drive_file_id, resolve_document_link
from ._errors import (
    GoogleAuthBrowserOpenError,
    GoogleAuthClientNotRegisteredError,
    GoogleAuthClientRevokedError,
    GoogleAuthError,
    GoogleAuthExpiredError,
    GoogleAuthKeychainLockedError,
    GoogleAuthLoopbackBindError,
    GoogleAuthNetworkError,
    GoogleAuthNonInteractiveError,
    GoogleAuthProfileUnboundError,
    GoogleAuthRevokedError,
    GoogleAuthScopeInsufficientError,
    GoogleAuthUnsecuredModeRefusedError,
    GoogleAuthValidationError,
)
from ._records import (
    DRIVE_FILE_SCOPE,
    REQUIRED_SCOPES,
    SHEETS_SCOPE,
    DriveAppProperties,
    OAuthClient,
    OAuthMetadata,
    OAuthToken,
)

__all__ = [
    "DRIVE_FILE_SCOPE",
    "REQUIRED_SCOPES",
    "SHEETS_SCOPE",
    "DriveAppProperties",
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
    "OAuthClient",
    "OAuthMetadata",
    "OAuthToken",
    "parse_drive_file_id",
    "resolve_document_link",
]
