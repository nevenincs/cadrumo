"""Pydantic records for the Google OAuth Desktop integration.

Three SecureObjectRepository-backed records anchor the per-profile
Google session: `OAuthClient` (the operator-imported Cloud Console
Desktop client JSON), `OAuthToken` (the refresh credential), and
`OAuthMetadata` (audit fields: granted scopes, account email,
issued/last-refreshed timestamps, reauth-required flag). One additional
record, `DriveAppProperties`, sits at the storage-adapter boundary and
encodes the Drive `appProperties` commit-log payload written on every
push. Every record is frozen, strict, and forbids extra fields.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The two scopes the desktop app requests at first login. The
# `drive.file` scope is non-sensitive and only grants access to files
# the app creates or the operator explicitly opens via the Drive
# picker. The `spreadsheets` scope is sensitive but works for the
# operator's own account inside Testing mode without going through
# verification.
DRIVE_FILE_SCOPE: str = "https://www.googleapis.com/auth/drive.file"
SHEETS_SCOPE: str = "https://www.googleapis.com/auth/spreadsheets"
REQUIRED_SCOPES: tuple[str, ...] = (DRIVE_FILE_SCOPE, SHEETS_SCOPE)


class OAuthClient(BaseModel):
    """Operator-imported Cloud Console Desktop OAuth client metadata.

    Carries the JSON the operator downloaded from the Cloud Console
    after creating a Desktop application OAuth client. The full
    `client_secret` is stored under the SECRET classification in the
    secure object repository; the `client_id` and `project_id` surface
    in status output for operator orientation.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    auth_uri: str = Field(min_length=1)
    token_uri: str = Field(min_length=1)
    auth_provider_x509_cert_url: str = Field(min_length=1)
    redirect_uris: tuple[str, ...] = Field(default=())

    @field_validator("auth_uri", "token_uri", "auth_provider_x509_cert_url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError(f"OAuth client URLs must use HTTPS; got {value!r}")
        return value


class OAuthToken(BaseModel):
    """The refresh credential issued by Google for a per-profile login.

    Stored under the SECRET classification in the secure object
    repository. The refresh token is re-persisted on every successful
    refresh because Google may rotate it. The access token is held in
    memory only — it is not persisted; rebuild it from the refresh
    token on next process start.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    refresh_token: str = Field(min_length=1)
    token_uri: str = Field(min_length=1)


class OAuthMetadata(BaseModel):
    """Audit fields surfaced by `aeat config google status` and refresh policy.

    None of these fields are secrets. They report which Google account
    the operator linked, which scopes the consent screen granted, when
    the credential was issued, when it was last refreshed, and whether
    the most recent refresh hit a hard `invalid_grant` requiring
    re-consent.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    account_email: str = Field(min_length=1)
    granted_scopes: tuple[str, ...] = Field(min_length=1)
    issued_at: datetime
    last_refresh_at: datetime
    reauth_required: bool = False

    @field_validator("granted_scopes")
    @classmethod
    def _require_drive_and_sheets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject metadata that omits either required scope.

        The CLI's `login` flow may only persist `OAuthMetadata` after
        the consent screen returns both scopes; this validator guards
        the in-memory model against accidental writes that would leave
        the integration unable to call Sheets or Drive.
        """

        missing = tuple(scope for scope in REQUIRED_SCOPES if scope not in value)
        if missing:
            raise ValueError(f"granted_scopes missing required scopes: {missing!r}")
        return value


class DriveAppProperties(BaseModel):
    """Drive `appProperties` commit-log payload written on every push.

    The Drive `appProperties` field tolerates up to 30 KB per file per
    app, which comfortably accommodates the small `(namespace, hmac,
    revision, source_hash, written_at, schema_version)` tuple that
    every mirrored object carries. The values surface in
    `files().list(fields="files(...,appProperties)")` calls without an
    extra API round-trip.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    object_key_hmac: str = Field(min_length=1)
    revision: int = Field(ge=1)
    source_hash: str = Field(min_length=1)
    written_at: datetime
    schema_version: str = Field(default="1", min_length=1)


__all__ = [
    "DRIVE_FILE_SCOPE",
    "DriveAppProperties",
    "OAuthClient",
    "OAuthMetadata",
    "OAuthToken",
    "REQUIRED_SCOPES",
    "SHEETS_SCOPE",
]
