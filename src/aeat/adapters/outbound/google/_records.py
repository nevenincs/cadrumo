"""Pydantic records for the Google OAuth and Drive configuration boundary.

The per-profile Google session persists :class:`OAuthClient`,
:class:`OAuthToken`, and :class:`OAuthMetadata` through
:mod:`aeat.adapters.outbound.google._session_store`. :class:`DriveConfig`
stores the Drive root folder selected for the profile and is read by
:func:`aeat.adapters.outbound.storage.get_storage_provider` when building the
Drive backend. :class:`DriveAppProperties` captures the typed
``appProperties`` commit-log schema at the storage boundary.

The OAuth scope constants come from :class:`Settings` and are bundled as
:data:`REQUIRED_SCOPES` for login, refresh, and validation flows. Every record
is frozen, strict, and forbids extra fields.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.config import Settings

# Scopes the desktop app requests at first login. Per Google's
# Identity Platform "Sign in with Google" guidance, an OAuth flow that
# needs to display *which* Google account is linked must request the
# `openid` + `userinfo.email` scope pair so Google returns a verifiable
# id_token carrying the user's email claim. The data-access scopes
# (`drive.file`, `spreadsheets`) cover the integration's substrate
# read/write surface. `drive.file` is non-sensitive (only files the
# app creates or the operator explicitly picks); `spreadsheets` is
# sensitive (full read/write) and surfaces on the consent screen.
# Reference: https://developers.google.com/identity/openid-connect/openid-connect
_SCOPES = Settings.external_constants().online_services.google.oauth_scopes
OPENID_SCOPE: str = _SCOPES.openid
EMAIL_SCOPE: str = _SCOPES.email
DRIVE_FILE_SCOPE: str = _SCOPES.drive_file
SHEETS_SCOPE: str = _SCOPES.spreadsheets
REQUIRED_SCOPES: tuple[str, ...] = (OPENID_SCOPE, EMAIL_SCOPE, DRIVE_FILE_SCOPE, SHEETS_SCOPE)


class OAuthClient(BaseModel):
    """Operator-imported Cloud Console Desktop OAuth client metadata.

    Carries the JSON the operator downloaded from the Cloud Console after
    creating a Desktop application OAuth client.
    :func:`~aeat.adapters.outbound.google._session_store.save_client` stores
    this record under the SECRET classification because ``client_secret`` is a
    long-lived credential. ``client_id`` and ``project_id`` can surface in
    status output for operator orientation.
    """

    model_config = STRICT_FROZEN_CONFIG

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

    :func:`~aeat.adapters.outbound.google._oauth_flow.run_login_flow` returns
    this record with :class:`OAuthMetadata`.
    :func:`~aeat.adapters.outbound.google._session_store.save_token` persists
    it under the SECRET classification. The refresh token is re-persisted on
    every successful refresh because Google may rotate it. Access tokens are
    held in memory only and rebuilt from the refresh token on process start.
    """

    model_config = STRICT_FROZEN_CONFIG

    refresh_token: str = Field(min_length=1)
    token_uri: str = Field(min_length=1)


class OAuthMetadata(BaseModel):
    """Audit fields surfaced by `aeat config google status` and refresh policy.

    This is the non-secret companion record to :class:`OAuthToken`.
    :func:`~aeat.adapters.outbound.google._session_store.save_metadata`
    persists which Google account the operator linked, which
    :data:`REQUIRED_SCOPES` the consent screen granted, when the credential was
    issued, when it was last refreshed, and whether the most recent refresh hit
    a hard ``invalid_grant`` requiring re-consent.
    """

    model_config = STRICT_FROZEN_CONFIG

    account_email: str = Field(min_length=1)
    granted_scopes: tuple[str, ...] = Field(min_length=1)
    issued_at: datetime
    last_refresh_at: datetime
    reauth_required: bool = False

    @field_validator("granted_scopes")
    @classmethod
    def _require_all_scopes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject metadata that omits any required scope.

        The CLI login flow may only persist :class:`OAuthMetadata` after the
        consent screen returns every scope in :data:`REQUIRED_SCOPES`
        (``openid`` + ``email`` + ``drive.file`` + ``spreadsheets``). Guards
        against accidental writes that would leave the integration unable to
        call Sheets, Drive, or display which account is linked.
        """
        missing = tuple(scope for scope in REQUIRED_SCOPES if scope not in value)
        if missing:
            raise ValueError(f"granted_scopes missing required scopes: {missing!r}")
        return value


class DriveConfig(BaseModel):
    """Per-profile Drive backend configuration persisted alongside OAuth records.

    :func:`~aeat.adapters.outbound.google._session_store.save_drive_config`
    persists the operator's chosen ``aeat-vault/`` parent folder id.
    :func:`aeat.adapters.outbound.storage.get_storage_provider` reads it after
    :class:`Settings`; the ``AEAT_GOOGLE_DRIVE_ROOT_FOLDER_ID`` setting remains
    an override for one-off and CI runs.
    """

    model_config = STRICT_FROZEN_CONFIG

    root_folder_id: str = Field(min_length=1)


class DriveAppProperties(BaseModel):
    """Typed Drive ``appProperties`` commit-log payload.

    The record validates the richer ``(namespace, object_key_hmac, revision,
    source_hash, written_at, schema_version)`` tuple at the Google boundary.
    The current
    :class:`~aeat.adapters.outbound.storage._google_drive.GoogleDriveProvider`
    write path does not instantiate this model; it writes ownership,
    namespace, full HMAC, and ``content_hash`` keys directly and maps them into
    :class:`aeat.adapters.outbound.storage.ProviderObjectMetadata`.
    """

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    object_key_hmac: str = Field(min_length=1)
    revision: int = Field(ge=1)
    source_hash: str = Field(min_length=1)
    written_at: datetime
    schema_version: str = Field(default="1", min_length=1)


__all__ = [
    "DRIVE_FILE_SCOPE",
    "EMAIL_SCOPE",
    "OPENID_SCOPE",
    "REQUIRED_SCOPES",
    "SHEETS_SCOPE",
    "DriveAppProperties",
    "DriveConfig",
    "OAuthClient",
    "OAuthMetadata",
    "OAuthToken",
]
