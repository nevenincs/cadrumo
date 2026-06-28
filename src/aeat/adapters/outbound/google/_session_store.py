"""Encrypted :class:`SecureObjectRepository` persistence for Google records.

Four per-profile record families back Google configuration and session state,
each under the namespace and :class:`SensitivityClass` declared by the storage
registry:

- :data:`GOOGLE_OAUTH_CLIENT_NAMESPACE` stores the operator-imported
  :class:`OAuthClient` at ``SensitivityClass.SECRET`` because
  ``client_secret`` is a long-lived credential.
- :data:`GOOGLE_OAUTH_TOKEN_NAMESPACE` stores the refresh :class:`OAuthToken`
  returned by :func:`aeat.adapters.outbound.google._oauth_flow.run_login_flow`
  at ``SensitivityClass.SECRET``.
- :data:`GOOGLE_OAUTH_METADATA_NAMESPACE` stores the non-secret
  :class:`OAuthMetadata` account, scope, issuance, refresh, and reauth audit
  fields at ``SensitivityClass.FINANCIAL``.
- :data:`GOOGLE_DRIVE_CONFIG_NAMESPACE` stores the :class:`DriveConfig` root
  folder selection used by :func:`aeat.adapters.outbound.storage.get_storage_provider`.

The public helpers use the profile identifier resolved by
:func:`aeat.adapters.outbound.google._active_profile.resolve_active_profile` as
the storage object key.
"""

from __future__ import annotations

from ....adapters.persistence.storage import (
    GOOGLE_DRIVE_CONFIG_NAMESPACE,
    GOOGLE_OAUTH_CLIENT_NAMESPACE,
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
)
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.classification import SensitivityClass
from ....core.external_constants import UTF_8_ENCODING
from ....core.time import now
from ._records import DriveConfig, OAuthClient, OAuthMetadata, OAuthToken

_NAMESPACE_CLIENT = GOOGLE_OAUTH_CLIENT_NAMESPACE.namespace
_NAMESPACE_TOKEN = GOOGLE_OAUTH_TOKEN_NAMESPACE.namespace
_NAMESPACE_METADATA = GOOGLE_OAUTH_METADATA_NAMESPACE.namespace
_NAMESPACE_DRIVE_CONFIG = GOOGLE_DRIVE_CONFIG_NAMESPACE.namespace
_RECORD_VERSION = 1


def save_client(profile: str, client: OAuthClient) -> None:
    """Persist an :class:`OAuthClient` for ``profile``.

    The record is written under :data:`GOOGLE_OAUTH_CLIENT_NAMESPACE` with
    ``SensitivityClass.SECRET`` so ``aeat config google login`` and Drive
    credential hydration can reload the operator-imported Desktop OAuth client.
    """
    _repository().save(
        namespace=_NAMESPACE_CLIENT,
        object_key=profile,
        classification=SensitivityClass.SECRET,
        schema_version=_RECORD_VERSION,
        written_at=now(),
        payload=client.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_client(profile: str) -> OAuthClient | None:
    """Load the :class:`OAuthClient` for ``profile``.

    Returns:
        The stored :class:`OAuthClient`, or ``None`` when the profile has not
        registered a Desktop OAuth client.
    """
    record = _repository().load(
        _NAMESPACE_CLIENT,
        profile,
        expected_class=SensitivityClass.SECRET,
        max_supported_version=_RECORD_VERSION,
    )
    if record is None:
        return None
    return OAuthClient.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def save_token(profile: str, token: OAuthToken) -> None:
    """Persist an :class:`OAuthToken` refresh credential for ``profile``.

    The token is written under :data:`GOOGLE_OAUTH_TOKEN_NAMESPACE` with
    ``SensitivityClass.SECRET``. The CLI saves this after
    :func:`aeat.adapters.outbound.google._oauth_flow.run_login_flow`, and
    refresh code may overwrite it when Google rotates the refresh token.
    """
    _repository().save(
        namespace=_NAMESPACE_TOKEN,
        object_key=profile,
        classification=SensitivityClass.SECRET,
        schema_version=_RECORD_VERSION,
        written_at=now(),
        payload=token.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_token(profile: str) -> OAuthToken | None:
    """Load the :class:`OAuthToken` refresh credential for ``profile``.

    Returns:
        The stored :class:`OAuthToken`, or ``None`` when the profile has no
        active Google login session.
    """
    record = _repository().load(
        _NAMESPACE_TOKEN,
        profile,
        expected_class=SensitivityClass.SECRET,
        max_supported_version=_RECORD_VERSION,
    )
    if record is None:
        return None
    return OAuthToken.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def save_metadata(profile: str, metadata: OAuthMetadata) -> None:
    """Persist :class:`OAuthMetadata` audit fields for ``profile``.

    Metadata is non-secret companion state for :class:`OAuthToken`: account
    email, granted scopes, issue/refresh timestamps, and reauth status. It is
    written under :data:`GOOGLE_OAUTH_METADATA_NAMESPACE` with
    ``SensitivityClass.FINANCIAL``.
    """
    _repository().save(
        namespace=_NAMESPACE_METADATA,
        object_key=profile,
        classification=SensitivityClass.FINANCIAL,
        schema_version=_RECORD_VERSION,
        written_at=now(),
        payload=metadata.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_metadata(profile: str) -> OAuthMetadata | None:
    """Load the :class:`OAuthMetadata` audit record for ``profile``.

    Returns:
        The stored :class:`OAuthMetadata`, or ``None`` when no metadata record
        exists for the profile.
    """
    record = _repository().load(
        _NAMESPACE_METADATA,
        profile,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_RECORD_VERSION,
    )
    if record is None:
        return None
    return OAuthMetadata.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def save_drive_config(profile: str, config: DriveConfig) -> None:
    """Persist the per-profile :class:`DriveConfig` backend selection.

    The config is written under :data:`GOOGLE_DRIVE_CONFIG_NAMESPACE` with
    ``SensitivityClass.FINANCIAL`` so
    :func:`aeat.adapters.outbound.storage.get_storage_provider` can resolve the
    Drive root folder without re-reading environment-only configuration.
    """
    _repository().save(
        namespace=_NAMESPACE_DRIVE_CONFIG,
        object_key=profile,
        classification=SensitivityClass.FINANCIAL,
        schema_version=_RECORD_VERSION,
        written_at=now(),
        payload=config.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_drive_config(profile: str) -> DriveConfig | None:
    """Load the per-profile :class:`DriveConfig` backend configuration.

    Returns:
        The stored :class:`DriveConfig`, or ``None`` when the profile has no
        persisted Drive root folder selection.
    """
    record = _repository().load(
        _NAMESPACE_DRIVE_CONFIG,
        profile,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_RECORD_VERSION,
    )
    if record is None:
        return None
    return DriveConfig.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def delete_session(profile: str) -> tuple[bool, bool]:
    """Delete the login session while preserving registration and Drive config.

    Removes only :class:`OAuthToken` and :class:`OAuthMetadata`, matching
    ``aeat config google logout``. The registered :class:`OAuthClient` and
    :class:`DriveConfig` remain available so a later login can reuse the Cloud
    Console JSON and the same Drive root folder.

    Args:
        profile: The profile identifier whose token and metadata records to
            delete.

    Returns:
        A pair ``(token_removed, metadata_removed)``.
    """
    repo = _repository()
    token_removed = repo.delete(_NAMESPACE_TOKEN, profile)
    metadata_removed = repo.delete(_NAMESPACE_METADATA, profile)
    return token_removed, metadata_removed


__all__ = [
    "delete_session",
    "load_client",
    "load_drive_config",
    "load_metadata",
    "load_token",
    "save_client",
    "save_drive_config",
    "save_metadata",
    "save_token",
]


def _repository() -> SecureObjectRepository:
    return secure_object_repository_for_active_bucket()
