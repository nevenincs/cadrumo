"""Encrypted :class:`SecureObjectRepository` persistence for Google OAuth records.

Three per-profile records back each Google session, each tagged with the
appropriate :class:`SensitivityClass`:

- `oauth-client` — operator-imported Cloud Console Desktop client JSON.
  Stored at SECRET class because `client_secret` is a long-lived credential.
- `oauth-token` — refresh token issued by the consent screen. SECRET class.
  Rotates after every successful refresh.
- `oauth-metadata` — audit fields (account email, granted scopes,
  issued/last-refreshed timestamps, reauth-required flag). FINANCIAL class
  because none of these fields are secrets but the presence of a Google
  session is operator-private state.

Each function is keyed on the resolved AEAT profile name (per
`_active_profile.resolve_active_profile`).
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
    """Persist the Cloud Console Desktop OAuth client for ``profile``."""
    _repository().save(
        namespace=_NAMESPACE_CLIENT,
        object_key=profile,
        classification=SensitivityClass.SECRET,
        schema_version=_RECORD_VERSION,
        written_at=now(),
        payload=client.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_client(profile: str) -> OAuthClient | None:
    """Load the :class:`OAuthClient` for ``profile``, or return ``None`` when absent."""
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
    """Persist the OAuth refresh token for ``profile``."""
    _repository().save(
        namespace=_NAMESPACE_TOKEN,
        object_key=profile,
        classification=SensitivityClass.SECRET,
        schema_version=_RECORD_VERSION,
        written_at=now(),
        payload=token.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_token(profile: str) -> OAuthToken | None:
    """Load the :class:`OAuthToken` refresh token for ``profile`` or return ``None``."""
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
    """Persist the OAuth audit metadata for ``profile``."""
    _repository().save(
        namespace=_NAMESPACE_METADATA,
        object_key=profile,
        classification=SensitivityClass.FINANCIAL,
        schema_version=_RECORD_VERSION,
        written_at=now(),
        payload=metadata.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_metadata(profile: str) -> OAuthMetadata | None:
    """Load the :class:`OAuthMetadata` audit record for ``profile``, or return ``None``."""
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
    """Persist the per-profile Drive backend configuration."""
    _repository().save(
        namespace=_NAMESPACE_DRIVE_CONFIG,
        object_key=profile,
        classification=SensitivityClass.FINANCIAL,
        schema_version=_RECORD_VERSION,
        written_at=now(),
        payload=config.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_drive_config(profile: str) -> DriveConfig | None:
    """Load the per-profile :class:`DriveConfig` backend configuration or return ``None``."""
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
    """Delete the refresh token and audit metadata; preserve the client and drive config.

    Args:
        profile: The profile identifier whose token and metadata records to delete.

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
