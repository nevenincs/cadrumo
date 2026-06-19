"""Google outbound adapter primitives: OAuth records and scopes.

Holds the typed OAuth client, token, and metadata records plus the Drive
and Sheets scope constants used by the read-only Google export mirror,
together with the Google auth error taxonomy. Google Sheets is a one-way
export mirror here, never an authority.

Major declarations:

* :class:`OAuthClient`, :class:`OAuthToken`, and :class:`OAuthMetadata` —
  the typed OAuth credential records.
* :data:`REQUIRED_SCOPES`, with :data:`DRIVE_FILE_SCOPE` and
  :data:`SHEETS_SCOPE` — the requested OAuth scopes.
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
