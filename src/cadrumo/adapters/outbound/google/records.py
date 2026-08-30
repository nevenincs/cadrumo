"""Pydantic records for the Google OAuth and Drive configuration boundary.

The per-profile Google session persists
:class:`adapters.outbound.google.OAuthClient`,
:class:`adapters.outbound.google.OAuthToken`, and
:class:`adapters.outbound.google.OAuthMetadata` through
:mod:`adapters.outbound.google.session_store`.
:class:`adapters.outbound.google.DriveConfig` stores the Drive root
folder selected for the profile and is read by
:func:`adapters.outbound.storage.get_storage_provider` when building the
Drive backend. :class:`adapters.outbound.google.DriveAppProperties`
captures the typed ``appProperties`` commit-log schema at the storage boundary.
See :mod:`adapters.outbound.google.impersonation` for
:class:`adapters.outbound.google.GoogleCredentialSourceSelection`, the
per-profile persisted choice of :class:`core.GoogleCredentialSourceKind`.

The OAuth scope constants come from :class:`core.config.Settings` and are
bundled as :data:`adapters.outbound.google.REQUIRED_SCOPES` for login,
refresh, and validation flows. Every record is frozen, strict, and forbids
extra fields.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG
from ....core.config import Settings
from ....core.time import UtcInstant

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


def _validate_google_oauth_endpoint(value: str, *, field_name: str, expected_host: str) -> str:
    """Validate one persisted OAuth endpoint before an upstream library consumes it."""
    endpoint = value.strip()
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field_name} must use a valid canonical Google HTTPS endpoint") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.hostname.lower() != expected_host
        or not parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{field_name} must be an absolute HTTPS endpoint on {expected_host!r} "
            "without userinfo, port, query, or fragment",
        )
    return endpoint


class OAuthClient(BaseModel):
    """Operator-imported Cloud Console Desktop OAuth client metadata.

    Carries the JSON the operator downloaded from the Cloud Console after
    creating a Desktop application OAuth client.
    :func:`adapters.outbound.google.save_client` stores
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

    @field_validator("auth_uri")
    @classmethod
    def _validate_auth_uri(cls, value: str) -> str:
        return _validate_google_oauth_endpoint(value, field_name="auth_uri", expected_host="accounts.google.com")

    @field_validator("token_uri")
    @classmethod
    def _validate_token_uri(cls, value: str) -> str:
        return _validate_google_oauth_endpoint(value, field_name="token_uri", expected_host="oauth2.googleapis.com")

    @field_validator("auth_provider_x509_cert_url")
    @classmethod
    def _validate_cert_uri(cls, value: str) -> str:
        return _validate_google_oauth_endpoint(
            value,
            field_name="auth_provider_x509_cert_url",
            expected_host="www.googleapis.com",
        )


class OAuthToken(BaseModel):
    """The refresh credential issued by Google for a per-profile login.

    :func:`adapters.outbound.google.run_login_flow` returns
    this record with :class:`adapters.outbound.google.OAuthMetadata`.
    :func:`adapters.outbound.google.save_token` persists
    it under the SECRET classification. The refresh token is re-persisted on
    every successful refresh because Google may rotate it. Access tokens are
    held in memory only and rebuilt from the refresh token on process start.
    """

    model_config = STRICT_FROZEN_CONFIG

    refresh_token: str = Field(min_length=1)
    token_uri: str = Field(min_length=1)

    @field_validator("refresh_token")
    @classmethod
    def _validate_refresh_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("refresh_token must contain a non-whitespace token")
        return value

    @field_validator("token_uri")
    @classmethod
    def _validate_token_uri(cls, value: str) -> str:
        return _validate_google_oauth_endpoint(value, field_name="token_uri", expected_host="oauth2.googleapis.com")


class OAuthMetadata(BaseModel):
    """Audit fields surfaced by `aeat config google status` and refresh policy.

    This is the non-secret companion record to
    :class:`adapters.outbound.google.OAuthToken`.
    :func:`adapters.outbound.google.save_metadata`
    persists which Google account the operator linked, which
    :data:`adapters.outbound.google.REQUIRED_SCOPES` the consent screen
    granted, when the credential was issued, when it was last refreshed, and
    whether the most recent refresh hit a hard ``invalid_grant`` requiring
    re-consent.
    """

    model_config = STRICT_FROZEN_CONFIG

    account_email: str = Field(min_length=1)
    granted_scopes: tuple[str, ...] = Field(min_length=1)
    # These audit instants survive encrypted persistence and the operator's
    # status projection, so their timezone policy belongs to the shared core
    # contract rather than to each producer and renderer.
    issued_at: UtcInstant
    last_refresh_at: UtcInstant
    reauth_required: bool = False

    @field_validator("granted_scopes")
    @classmethod
    def _require_all_scopes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject metadata that omits any required scope.

        The CLI login flow may only persist
        :class:`adapters.outbound.google.OAuthMetadata` after the consent
        screen returns every scope in
        :data:`adapters.outbound.google.REQUIRED_SCOPES` (``openid`` +
        ``email`` + ``drive.file`` + ``spreadsheets``). Guards against
        accidental writes that would leave the integration unable to call
        Sheets, Drive, or display which account is linked.
        """
        missing = tuple(scope for scope in REQUIRED_SCOPES if scope not in value)
        if missing:
            raise ValueError(f"granted_scopes missing required scopes: {missing!r}")
        return value


class DriveConfig(BaseModel):
    """Per-profile Drive backend configuration persisted alongside OAuth records.

    :func:`adapters.outbound.google.save_drive_config`
    persists the operator's chosen ``cadrumo-vault/`` parent folder id.
    :func:`adapters.outbound.storage.get_storage_provider` reads it after
    :class:`core.config.Settings`; the
    ``CADRUMO_GOOGLE_DRIVE_ROOT_FOLDER_ID`` setting remains an override for
    one-off and CI runs.
    """

    model_config = STRICT_FROZEN_CONFIG

    root_folder_id: str = Field(min_length=1)


class DriveAppProperties(BaseModel):
    """Typed ``appProperties`` payload used by the Drive storage provider."""

    model_config = STRICT_FROZEN_CONFIG

    ownership_marker: Literal["cadrumo"] = Field(alias="cadrumo_vault_app")
    namespace: str = Field(min_length=1)
    object_key_hmac: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)


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
