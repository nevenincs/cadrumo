"""Pydantic records for the Google OAuth and Drive configuration boundary.

:class:`adapters.outbound.google.records.OAuthClient` is the publisher's Desktop
client, read from installation data by
:func:`adapters.outbound.google.installation_client.load_installation_client`.
The per-profile Google session persists
:class:`adapters.outbound.google.records.OAuthToken` and
:class:`adapters.outbound.google.records.OAuthMetadata` through
:mod:`adapters.outbound.google.session_store`.
:class:`adapters.outbound.google.records.DriveConfig` stores the Drive root
folder selected for the profile and is read by
:func:`adapters.outbound.storage.factory.get_storage_provider` when building the
Drive backend. :class:`adapters.outbound.google.records.DriveAppProperties`
captures the typed ``appProperties`` commit-log schema at the storage boundary.

The OAuth scope constants come from :class:`core.config.Settings` and are
bundled as :data:`adapters.outbound.google.records.REQUIRED_SCOPES` for login,
refresh, and validation flows. Every record is frozen, strict, and forbids
extra fields.
"""

from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import SplitResult, urlsplit

from pydantic import AfterValidator, BaseModel, Field, field_validator

from ....core.config import Settings
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.time.utc import UtcInstant

# Scopes the desktop app requests at sign-in. An OAuth flow that needs to
# display *which* Google account is linked must request the `openid` +
# `userinfo.email` pair so Google returns a verifiable id_token carrying
# the user's email claim. `drive.file` is the only data-access scope: it is
# non-sensitive and reaches only files this application created, which is
# all the export and its readback are meant to touch.
# Reference: https://developers.google.com/identity/openid-connect/openid-connect
_SCOPES = Settings.external_constants().online_services.google.oauth_scopes
OPENID_SCOPE: str = _SCOPES.openid
EMAIL_SCOPE: str = _SCOPES.email
DRIVE_FILE_SCOPE: str = _SCOPES.drive_file
REQUIRED_SCOPES: tuple[str, ...] = (OPENID_SCOPE, EMAIL_SCOPE, DRIVE_FILE_SCOPE)


def _google_oauth_endpoint_has_https_hostname(parsed: SplitResult) -> bool:
    """Require the endpoint transport and a hostname before later checks."""
    return parsed.scheme == "https" and parsed.hostname is not None


def _google_oauth_endpoint_has_no_userinfo_or_port(parsed: SplitResult, port: int | None) -> bool:
    """Reject credentials and explicit ports before matching the host."""
    return parsed.username is None and parsed.password is None and port is None


def _google_oauth_endpoint_matches_host(parsed: SplitResult, expected_host: str) -> bool:
    """Compare the normalised parsed hostname with its canonical Google host."""
    hostname = parsed.hostname
    return hostname is not None and hostname.lower() == expected_host


def _google_oauth_endpoint_has_clean_path(parsed: SplitResult) -> bool:
    """Require a path while refusing query and fragment components."""
    if not parsed.path:
        return False
    return not parsed.query and not parsed.fragment


def _validate_google_oauth_endpoint(value: str, *, field_name: str, expected_host: str) -> str:
    """Validate one persisted OAuth endpoint before an upstream library consumes it."""
    endpoint = value.strip()
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field_name} must use a valid canonical Google HTTPS endpoint") from exc
    if (
        not _google_oauth_endpoint_has_https_hostname(parsed)
        or not _google_oauth_endpoint_has_no_userinfo_or_port(parsed, port)
        or not _google_oauth_endpoint_matches_host(parsed, expected_host)
        or not _google_oauth_endpoint_has_clean_path(parsed)
    ):
        raise ValueError(
            f"{field_name} must be an absolute HTTPS endpoint on {expected_host!r} "
            "without userinfo, port, query, or fragment",
        )
    return endpoint


def _validate_token_uri(value: str) -> str:
    return _validate_google_oauth_endpoint(value, field_name="token_uri", expected_host="oauth2.googleapis.com")


OAuthTokenUri = Annotated[str, Field(min_length=1), AfterValidator(_validate_token_uri)]
"""A Google OAuth token endpoint, refused unless it is the canonical HTTPS host."""


class OAuthClient(BaseModel):
    """The publisher's Google OAuth Desktop client metadata.

    Carries the fields of a Desktop client download from the Google Cloud
    Console. It is installation data, the same for every profile, and is
    never persisted as a profile record. Google does not treat an installed
    application's ``client_secret`` as confidential, so the record is not a
    stored secret either; it still never enters command output or logs.
    """

    model_config = STRICT_FROZEN_CONFIG

    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    auth_uri: str = Field(min_length=1)
    token_uri: OAuthTokenUri
    auth_provider_x509_cert_url: str = Field(min_length=1)
    redirect_uris: tuple[str, ...] = Field(default=())

    @field_validator("auth_uri")
    @classmethod
    @pydantic_validation_boundary
    def _validate_auth_uri(cls, value: str) -> str:
        return _validate_google_oauth_endpoint(value, field_name="auth_uri", expected_host="accounts.google.com")

    @field_validator("auth_provider_x509_cert_url")
    @classmethod
    @pydantic_validation_boundary
    def _validate_cert_uri(cls, value: str) -> str:
        return _validate_google_oauth_endpoint(
            value,
            field_name="auth_provider_x509_cert_url",
            expected_host="www.googleapis.com",
        )


class OAuthToken(BaseModel):
    """The refresh credential issued by Google for a per-profile login.

    :func:`adapters.outbound.google.oauth_flow.run_login_flow` returns
    this record with :class:`adapters.outbound.google.records.OAuthMetadata`.
    :func:`adapters.outbound.google.session_store.save_token` persists
    it under the SECRET classification. The refresh token is re-persisted on
    every successful refresh because Google may rotate it. Access tokens are
    held in memory only and rebuilt from the refresh token on process start.
    """

    model_config = STRICT_FROZEN_CONFIG

    refresh_token: str = Field(min_length=1)
    token_uri: OAuthTokenUri

    @field_validator("refresh_token")
    @classmethod
    @pydantic_validation_boundary
    def _validate_refresh_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("refresh_token must contain a non-whitespace token")
        return value


class OAuthMetadata(BaseModel):
    """Audit fields surfaced by `aeat config google status` and refresh policy.

    This is the non-secret companion record to
    :class:`adapters.outbound.google.records.OAuthToken`.
    :func:`adapters.outbound.google.session_store.save_metadata`
    persists which Google account the operator linked, which
    :data:`adapters.outbound.google.records.REQUIRED_SCOPES` the consent screen
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
    @pydantic_validation_boundary
    def _require_all_scopes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject metadata that omits any required scope.

        The CLI login flow may only persist
        :class:`adapters.outbound.google.records.OAuthMetadata` after the consent
        screen returns every scope in
        :data:`adapters.outbound.google.records.REQUIRED_SCOPES` (``openid`` +
        ``email`` + ``drive.file``). Guards against accidental writes that
        would leave the integration unable to call Sheets, Drive, or display
        which account is linked.
        """
        missing = tuple(scope for scope in REQUIRED_SCOPES if scope not in value)
        if missing:
            raise ValueError(f"granted_scopes missing required scopes: {missing!r}")
        return value


class DriveConfig(BaseModel):
    """Per-profile Drive backend configuration persisted alongside OAuth records.

    :func:`adapters.outbound.google.session_store.save_drive_config`
    persists the operator's chosen ``cadrumo-vault/`` parent folder id.
    :func:`adapters.outbound.storage.factory.get_storage_provider` reads it after
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
    "DriveAppProperties",
    "DriveConfig",
    "OAuthClient",
    "OAuthMetadata",
    "OAuthToken",
]
