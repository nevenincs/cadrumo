"""Public re-exports for Google outbound adapter primitives.

This package boundary exposes OAuth records and scope constants from
:mod:`adapters.outbound.google._records`, the Google auth error taxonomy from
:mod:`adapters.outbound.google.errors`, and scoped document-link helpers from
:mod:`adapters.outbound.google._document_link_resolver`. Google Sheets
remains a one-way export mirror here, never an authority.

The Drive document-link helper follows the integration's minimal-scope posture:
``drive.file`` links the app can reach are fetched as bytes for callers to store
as encrypted evidence, while Gmail links, arbitrary URLs, and Drive files that
need broader read scopes are refused instead of being stored as link-only
evidence.

Major declarations:

* :class:`OAuthClient`,
  :class:`OAuthToken`, and
  :class:`OAuthMetadata` — the typed OAuth
  credential records.
* :class:`DriveAppProperties` — the typed Drive
  ``appProperties`` payload.
* :class:`DriveConfig` — the typed per-profile
  Drive/Sheets config record.
* :data:`REQUIRED_SCOPES`, with
  :data:`DRIVE_FILE_SCOPE` and
  :data:`SHEETS_SCOPE` — the requested OAuth
  scopes.
* :func:`parse_drive_file_id` and
  :func:`resolve_document_link` — the
  minimal-scope Drive document-link helpers.
* :func:`list_drive_folder_documents`, returning a
  :class:`DriveFolderListing` of
  :class:`DriveFolderDocument` rows — the
  minimal-scope Drive folder bulk-listing helper.
* :exc:`GoogleAuthError` and its subclasses —
  the Google auth failure taxonomy.
* :func:`run_login_flow` — the interactive OAuth
  login flow.
* :func:`save_client`,
  :func:`load_client`,
  :func:`save_token`,
  :func:`load_token`,
  :func:`save_metadata`,
  :func:`load_metadata`,
  :func:`save_drive_config`,
  :func:`load_drive_config`, and
  :func:`delete_session` — the per-profile
  session-store primitives.
* :func:`resolve_active_profile` — the
  active-profile resolver.
* :class:`CalcSheetsApplyResult` and
  :func:`apply_export_plan` — the
  export-plan-to-Sheets apply surface.
* :class:`CalcSheetsExportPreview` and
  :func:`preview_export_plan` — the read-only
  dry-run preview of the same apply surface.
* :class:`RowSetEdit`,
  :class:`PullResult`,
  :func:`pull_operator_edits`, and
  :func:`compute_from_pull` — the operator-edit
  pull surface.
* :class:`GoogleImpersonationConfig`,
  :func:`resolve_impersonated_credentials`, and
  :func:`describe_impersonation_target` — the service-account
  impersonation credential source
  (:attr:`~core.GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION`),
  an alternative to the default OAuth Desktop flow above.
* :class:`GoogleCredentialSourceSelection`,
  :func:`save_credential_source_selection`, and
  :func:`load_credential_source_selection` — per-profile persistence of
  which :class:`~core.GoogleCredentialSourceKind` a profile has chosen,
  consumed by :func:`~adapters.outbound.storage.build_google_credentials`
  to dispatch between the OAuth-Desktop and impersonation sources.

See Also:
    - :mod:`adapters.outbound.storage` for the Google Drive storage
      mirror that owns remote ciphertext synchronisation.
    - :mod:`domain.attachments` for byte-bearing attachment records that
      consume resolved Drive document bytes.
"""

from ._active_profile import resolve_active_profile
from ._api import GoogleApiResponseBody, GoogleDriveFile, GoogleSheetsRange, GoogleSpreadsheet
from ._calc_sheets_apply import CalcSheetsApplyResult, CalcSheetsExportPreview, apply_export_plan, preview_export_plan
from ._calc_sheets_pull import (
    PullResult,
    RowSetCellEdit,
    RowSetEdit,
    compute_from_pull,
    pull_operator_edits,
    relation_edit_payload,
)
from ._document_link_resolver import (
    DriveFolderDocument,
    DriveFolderListing,
    list_drive_folder_documents,
    parse_drive_file_id,
    resolve_document_link,
)
from ._impersonation import (
    GoogleAuthAdcStaleError,
    GoogleAuthAdcUnavailableError,
    GoogleAuthImpersonationRefusedError,
    GoogleCredentialSourceSelection,
    GoogleImpersonationConfig,
    describe_impersonation_target,
    resolve_impersonated_credentials,
)
from ._oauth_flow import run_login_flow
from ._records import (
    DRIVE_FILE_SCOPE,
    REQUIRED_SCOPES,
    SHEETS_SCOPE,
    DriveAppProperties,
    DriveConfig,
    OAuthClient,
    OAuthMetadata,
    OAuthToken,
)
from .errors import (
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
from .session_store import (
    delete_session,
    load_client,
    load_credential_source_selection,
    load_drive_config,
    load_metadata,
    load_token,
    save_client,
    save_credential_source_selection,
    save_drive_config,
    save_metadata,
    save_token,
)

__all__ = [
    "DRIVE_FILE_SCOPE",
    "REQUIRED_SCOPES",
    "SHEETS_SCOPE",
    "CalcSheetsApplyResult",
    "CalcSheetsExportPreview",
    "DriveAppProperties",
    "DriveConfig",
    "DriveFolderDocument",
    "DriveFolderListing",
    "GoogleApiResponseBody",
    "GoogleAuthAdcStaleError",
    "GoogleAuthAdcUnavailableError",
    "GoogleAuthBrowserOpenError",
    "GoogleAuthClientNotRegisteredError",
    "GoogleAuthClientRevokedError",
    "GoogleAuthError",
    "GoogleAuthExpiredError",
    "GoogleAuthImpersonationRefusedError",
    "GoogleAuthKeychainLockedError",
    "GoogleAuthLoopbackBindError",
    "GoogleAuthNetworkError",
    "GoogleAuthNonInteractiveError",
    "GoogleAuthProfileUnboundError",
    "GoogleAuthRevokedError",
    "GoogleAuthScopeInsufficientError",
    "GoogleAuthUnsecuredModeRefusedError",
    "GoogleAuthValidationError",
    "GoogleCredentialSourceSelection",
    "GoogleDriveFile",
    "GoogleImpersonationConfig",
    "GoogleSheetsRange",
    "GoogleSpreadsheet",
    "OAuthClient",
    "OAuthMetadata",
    "OAuthToken",
    "PullResult",
    "RowSetCellEdit",
    "RowSetEdit",
    "apply_export_plan",
    "compute_from_pull",
    "delete_session",
    "describe_impersonation_target",
    "list_drive_folder_documents",
    "load_client",
    "load_credential_source_selection",
    "load_drive_config",
    "load_metadata",
    "load_token",
    "parse_drive_file_id",
    "preview_export_plan",
    "pull_operator_edits",
    "relation_edit_payload",
    "resolve_active_profile",
    "resolve_document_link",
    "resolve_impersonated_credentials",
    "run_login_flow",
    "save_client",
    "save_credential_source_selection",
    "save_drive_config",
    "save_metadata",
    "save_token",
]
