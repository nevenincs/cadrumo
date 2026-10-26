"""Seed individual Google records for deliberately partial test states."""

from .....core.external_constants import UTF_8_ENCODING
from .....core.time.clock import now
from ....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....persistence.storage.secure_object_namespaces import (
    GOOGLE_DRIVE_CONFIG_NAMESPACE,
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
)
from ..records import DriveConfig, OAuthMetadata, OAuthToken


def _save(profile: str, record: DriveConfig | OAuthMetadata | OAuthToken) -> None:
    definition = (
        GOOGLE_OAUTH_TOKEN_NAMESPACE
        if isinstance(record, OAuthToken)
        else GOOGLE_OAUTH_METADATA_NAMESPACE
        if isinstance(record, OAuthMetadata)
        else GOOGLE_DRIVE_CONFIG_NAMESPACE
    )
    secure_object_repository_for_active_bucket().save(
        namespace=definition.namespace,
        object_key=profile,
        classification=definition.sensitivity,
        schema_version=definition.schema_version,
        written_at=now(),
        payload=record.model_dump_json().encode(UTF_8_ENCODING),
    )


def save_token(profile: str, token: OAuthToken) -> None:
    """Seed a test token through the real encrypted repository."""
    _save(profile, token)


def save_metadata(profile: str, metadata: OAuthMetadata) -> None:
    """Seed test account metadata through the real encrypted repository."""
    _save(profile, metadata)


def save_drive_config(profile: str, config: DriveConfig) -> None:
    """Seed a test root locator through the real encrypted repository."""
    _save(profile, config)
