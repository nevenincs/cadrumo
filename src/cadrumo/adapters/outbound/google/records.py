"""Pydantic records for the Google OAuth and Drive configuration boundary.

:class:`core.config_google_client.OAuthClient` is the publisher's Desktop
client, read from installation data by
:func:`adapters.outbound.google.installation_client.load_installation_client`.
The per-profile Google session persists
:class:`adapters.outbound.google.records.OAuthToken` and
:class:`adapters.outbound.google.records.OAuthMetadata` through
:mod:`adapters.outbound.google.session_store`.
:class:`adapters.outbound.google.records.DriveConfig` stores the Drive root
folder created for the profile and is read by
:func:`adapters.outbound.storage.factory.get_storage_provider` when building the
Drive backend. :class:`adapters.outbound.google.records.DriveAppProperties`
captures the typed ``appProperties`` commit-log schema at the storage boundary.

The OAuth scope constants come from :class:`core.config.Settings` and are
bundled as :data:`adapters.outbound.google.records.REQUIRED_SCOPES` for login,
refresh, and validation flows. Every record is frozen, strict, and forbids
extra fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ....core.config import Settings
from ....core.config_google_client import OAuthTokenUri
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


class OAuthToken(BaseModel):
    """The refresh credential issued by Google for a per-profile login.

    :func:`adapters.outbound.google.oauth_flow.run_login_flow` returns
    this record with :class:`adapters.outbound.google.records.OAuthMetadata`.
    :func:`adapters.outbound.google.session_store.save_session` persists
    it under the SECRET classification. It is written once, at sign-in.
    Access tokens are held in memory only and rebuilt from the refresh token
    on process start.

    ``client_id`` names the client that minted the token. A refresh token is
    only valid with that client, so the token is never presented with
    another one.
    """

    model_config = STRICT_FROZEN_CONFIG

    refresh_token: str = Field(min_length=1, repr=False)
    client_id: str = Field(min_length=1)
    token_uri: OAuthTokenUri

    @field_validator("refresh_token")
    @classmethod
    @pydantic_validation_boundary
    def _validate_refresh_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("refresh_token must contain a non-whitespace token")
        return value


class OAuthMetadata(BaseModel):
    """Audit fields surfaced by `aeat config google status`.

    This is the non-secret companion record to
    :class:`adapters.outbound.google.records.OAuthToken`.
    :func:`adapters.outbound.google.session_store.save_session`
    persists which Google account the operator linked, which
    :data:`adapters.outbound.google.records.REQUIRED_SCOPES` the consent screen
    granted, and when the credential was issued. It records the sign-in, not
    what happened to the grant afterwards: nothing observes a later refresh.
    """

    model_config = STRICT_FROZEN_CONFIG

    account_email: str = Field(min_length=1)
    granted_scopes: tuple[str, ...] = Field(min_length=1)
    # This audit instant survives encrypted persistence and the operator's
    # status projection, so its timezone policy belongs to the shared core
    # contract rather than to each producer and renderer.
    issued_at: UtcInstant

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

    :func:`adapters.outbound.google.session_store.save_session`
    persists the ID of the folder
    :func:`adapters.outbound.google.root_folder.ensure_profile_root_folder`
    created at sign-in. Nothing else writes it: no command, setting or
    environment variable supplies a Drive folder.
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
    "OAuthMetadata",
    "OAuthToken",
]
