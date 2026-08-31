"""Encrypted Google record persistence.

This module writes Google records through
:class:`adapters.persistence.storage.SecureObjectRepository`.

Five per-profile record families back Google configuration and session state,
each under the namespace and
:class:`adapters.persistence.storage.SensitivityClass` declared by the
storage registry:

- :data:`adapters.persistence.storage.GOOGLE_OAUTH_CLIENT_NAMESPACE`
  stores the operator-imported
  :class:`adapters.outbound.google.OAuthClient` at ``SECRET``
  sensitivity because ``client_secret`` is a long-lived credential.
- :data:`adapters.persistence.storage.GOOGLE_OAUTH_TOKEN_NAMESPACE`
  stores the refresh :class:`adapters.outbound.google.OAuthToken`
  returned by :func:`adapters.outbound.google.run_login_flow` at
  ``SECRET`` sensitivity.
- :data:`adapters.persistence.storage.GOOGLE_OAUTH_METADATA_NAMESPACE`
  stores the non-secret
  :class:`adapters.outbound.google.OAuthMetadata` account, scope,
  issuance, refresh, and reauth audit fields at ``FINANCIAL`` sensitivity.
- :data:`adapters.persistence.storage.GOOGLE_DRIVE_CONFIG_NAMESPACE`
  stores the :class:`adapters.outbound.google.DriveConfig` root folder
  selection used by
  :func:`adapters.outbound.storage.get_storage_provider` at
  ``FINANCIAL`` sensitivity.
- :data:`adapters.persistence.storage.GOOGLE_CREDENTIAL_SOURCE_NAMESPACE`
  stores the :class:`adapters.outbound.google.GoogleCredentialSourceSelection`
  choice of :class:`core.GoogleCredentialSourceKind` (and, for
  service-account impersonation, the target SA email/scopes) at
  ``FINANCIAL`` sensitivity — configuration only, never a credential.

The public helpers use the profile identifier resolved by
:func:`adapters.outbound.google.resolve_active_profile` as the storage
object key, matching the ``{profile}`` grammar on all five namespace
definitions.
"""

from __future__ import annotations

from ....adapters.persistence.storage.crypto.encrypted_columns import secure_object_key_digest
from ....core.external_constants import UTF_8_ENCODING
from ....core.time.clock import now
from ...persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...persistence.storage.secure_object_namespaces import (
    GOOGLE_CREDENTIAL_SOURCE_NAMESPACE,
    GOOGLE_DRIVE_CONFIG_NAMESPACE,
    GOOGLE_OAUTH_CLIENT_NAMESPACE,
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
)
from ...persistence.storage.sql import SecureObjectDeletion, SecureObjectRepository
from .impersonation import GoogleCredentialSourceSelection
from .records import DriveConfig, OAuthClient, OAuthMetadata, OAuthToken

_NAMESPACE_CLIENT = GOOGLE_OAUTH_CLIENT_NAMESPACE.namespace
_NAMESPACE_TOKEN = GOOGLE_OAUTH_TOKEN_NAMESPACE.namespace
_NAMESPACE_METADATA = GOOGLE_OAUTH_METADATA_NAMESPACE.namespace
_NAMESPACE_DRIVE_CONFIG = GOOGLE_DRIVE_CONFIG_NAMESPACE.namespace
_NAMESPACE_CREDENTIAL_SOURCE = GOOGLE_CREDENTIAL_SOURCE_NAMESPACE.namespace
_CLIENT_SENSITIVITY = GOOGLE_OAUTH_CLIENT_NAMESPACE.sensitivity
_CLIENT_VERSION = GOOGLE_OAUTH_CLIENT_NAMESPACE.schema_version
_TOKEN_SENSITIVITY = GOOGLE_OAUTH_TOKEN_NAMESPACE.sensitivity
_TOKEN_VERSION = GOOGLE_OAUTH_TOKEN_NAMESPACE.schema_version
_METADATA_SENSITIVITY = GOOGLE_OAUTH_METADATA_NAMESPACE.sensitivity
_METADATA_VERSION = GOOGLE_OAUTH_METADATA_NAMESPACE.schema_version
_DRIVE_CONFIG_SENSITIVITY = GOOGLE_DRIVE_CONFIG_NAMESPACE.sensitivity
_DRIVE_CONFIG_VERSION = GOOGLE_DRIVE_CONFIG_NAMESPACE.schema_version
_CREDENTIAL_SOURCE_SENSITIVITY = GOOGLE_CREDENTIAL_SOURCE_NAMESPACE.sensitivity
_CREDENTIAL_SOURCE_VERSION = GOOGLE_CREDENTIAL_SOURCE_NAMESPACE.schema_version


def save_client(profile: str, client: OAuthClient) -> None:
    """Persist an :class:`adapters.outbound.google.OAuthClient` for ``profile``.

    The record is written under
    :data:`adapters.persistence.storage.GOOGLE_OAUTH_CLIENT_NAMESPACE`
    with :class:`adapters.persistence.storage.SensitivityClass`
    ``SECRET`` so ``aeat config google login`` and Drive credential hydration
    can reload the operator-imported Desktop OAuth client.
    """
    _repository().save(
        namespace=_NAMESPACE_CLIENT,
        object_key=profile,
        classification=_CLIENT_SENSITIVITY,
        schema_version=_CLIENT_VERSION,
        written_at=now(),
        payload=client.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_client(profile: str) -> OAuthClient | None:
    """Load the :class:`adapters.outbound.google.OAuthClient` for ``profile``.

    Returns:
        The stored :class:`adapters.outbound.google.OAuthClient`, or
        ``None`` when the profile has not registered a Desktop OAuth client.
    """
    record = _repository().load(
        _NAMESPACE_CLIENT,
        profile,
        expected_class=_CLIENT_SENSITIVITY,
        max_supported_version=_CLIENT_VERSION,
    )
    if record is None:
        return None
    return OAuthClient.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def save_token(profile: str, token: OAuthToken) -> None:
    """Persist an :class:`adapters.outbound.google.OAuthToken` for ``profile``.

    The token is written under
    :data:`adapters.persistence.storage.GOOGLE_OAUTH_TOKEN_NAMESPACE`
    with :class:`adapters.persistence.storage.SensitivityClass`
    ``SECRET``. The CLI saves this after
    :func:`adapters.outbound.google.run_login_flow`, and
    refresh code may overwrite it when Google rotates the refresh token.
    """
    _repository().save(
        namespace=_NAMESPACE_TOKEN,
        object_key=profile,
        classification=_TOKEN_SENSITIVITY,
        schema_version=_TOKEN_VERSION,
        written_at=now(),
        payload=token.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_token(profile: str) -> OAuthToken | None:
    """Load the :class:`adapters.outbound.google.OAuthToken` for ``profile``.

    Returns:
        The stored :class:`adapters.outbound.google.OAuthToken`, or
        ``None`` when the profile has no active Google login session.
    """
    record = _repository().load(
        _NAMESPACE_TOKEN,
        profile,
        expected_class=_TOKEN_SENSITIVITY,
        max_supported_version=_TOKEN_VERSION,
    )
    if record is None:
        return None
    return OAuthToken.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def save_metadata(profile: str, metadata: OAuthMetadata) -> None:
    """Persist :class:`adapters.outbound.google.OAuthMetadata` for ``profile``.

    Metadata is non-secret companion state for
    :class:`adapters.outbound.google.OAuthToken`: account email, granted
    scopes, issue/refresh timestamps, and reauth status. It is written under
    :data:`adapters.persistence.storage.GOOGLE_OAUTH_METADATA_NAMESPACE`
    with :class:`adapters.persistence.storage.SensitivityClass`
    ``FINANCIAL``.
    """
    _repository().save(
        namespace=_NAMESPACE_METADATA,
        object_key=profile,
        classification=_METADATA_SENSITIVITY,
        schema_version=_METADATA_VERSION,
        written_at=now(),
        payload=metadata.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_metadata(profile: str) -> OAuthMetadata | None:
    """Load the :class:`adapters.outbound.google.OAuthMetadata` for ``profile``.

    Returns:
        The stored :class:`adapters.outbound.google.OAuthMetadata`, or
        ``None`` when no metadata record exists for the profile.
    """
    record = _repository().load(
        _NAMESPACE_METADATA,
        profile,
        expected_class=_METADATA_SENSITIVITY,
        max_supported_version=_METADATA_VERSION,
    )
    if record is None:
        return None
    return OAuthMetadata.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def save_drive_config(profile: str, config: DriveConfig) -> None:
    """Persist the per-profile :class:`adapters.outbound.google.DriveConfig`.

    The config is written under
    :data:`adapters.persistence.storage.GOOGLE_DRIVE_CONFIG_NAMESPACE`
    with :class:`adapters.persistence.storage.SensitivityClass`
    ``FINANCIAL`` so
    :func:`adapters.outbound.storage.get_storage_provider` can resolve
    the Drive root folder without re-reading environment-only configuration.
    """
    _repository().save(
        namespace=_NAMESPACE_DRIVE_CONFIG,
        object_key=profile,
        classification=_DRIVE_CONFIG_SENSITIVITY,
        schema_version=_DRIVE_CONFIG_VERSION,
        written_at=now(),
        payload=config.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_drive_config(profile: str) -> DriveConfig | None:
    """Load the per-profile :class:`adapters.outbound.google.DriveConfig`.

    Returns:
        The stored :class:`adapters.outbound.google.DriveConfig`, or
        ``None`` when the profile has no persisted Drive root folder selection.
    """
    record = _repository().load(
        _NAMESPACE_DRIVE_CONFIG,
        profile,
        expected_class=_DRIVE_CONFIG_SENSITIVITY,
        max_supported_version=_DRIVE_CONFIG_VERSION,
    )
    if record is None:
        return None
    return DriveConfig.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def save_credential_source_selection(profile: str, selection: GoogleCredentialSourceSelection) -> None:
    """Persist the per-profile :class:`adapters.outbound.google.GoogleCredentialSourceSelection`.

    The record is written under
    :data:`adapters.persistence.storage.GOOGLE_CREDENTIAL_SOURCE_NAMESPACE`
    with :class:`adapters.persistence.storage.SensitivityClass`
    ``FINANCIAL`` so
    :func:`adapters.outbound.storage.build_google_credentials` can dispatch
    to the chosen :class:`core.GoogleCredentialSourceKind` without
    re-reading environment-only configuration. No long-lived secret rides
    on this record: the impersonated access token is re-derived from
    Application Default Credentials on every use and is never persisted.
    """
    _repository().save(
        namespace=_NAMESPACE_CREDENTIAL_SOURCE,
        object_key=profile,
        classification=_CREDENTIAL_SOURCE_SENSITIVITY,
        schema_version=_CREDENTIAL_SOURCE_VERSION,
        written_at=now(),
        payload=selection.model_dump_json().encode(UTF_8_ENCODING),
    )


def load_credential_source_selection(profile: str) -> GoogleCredentialSourceSelection | None:
    """Load the per-profile :class:`adapters.outbound.google.GoogleCredentialSourceSelection`.

    Returns:
        The stored :class:`adapters.outbound.google.GoogleCredentialSourceSelection`,
        or ``None`` when the profile has no persisted selection. A ``None``
        result means the default
        :attr:`core.GoogleCredentialSourceKind.OAUTH_DESKTOP` path applies —
        callers must not treat a missing record as an error.
    """
    record = _repository().load(
        _NAMESPACE_CREDENTIAL_SOURCE,
        profile,
        expected_class=_CREDENTIAL_SOURCE_SENSITIVITY,
        max_supported_version=_CREDENTIAL_SOURCE_VERSION,
    )
    if record is None:
        return None
    return GoogleCredentialSourceSelection.model_validate_json(record.payload.decode(UTF_8_ENCODING))


def delete_session(profile: str) -> tuple[bool, bool]:
    """Delete the login session while preserving registration and Drive config.

    Removes only the
    :data:`adapters.persistence.storage.GOOGLE_OAUTH_TOKEN_NAMESPACE` and
    :data:`adapters.persistence.storage.GOOGLE_OAUTH_METADATA_NAMESPACE`
    records, matching ``aeat config google logout``. The registered
    :class:`adapters.outbound.google.OAuthClient` and
    :class:`adapters.outbound.google.DriveConfig` remain available so a
    later login can reuse the Cloud Console JSON and the same Drive root
    folder.

    The token and its companion metadata are one logout, so they are removed
    in ONE unit of work. They used to be two independent commits: a failure on
    the second left the token gone and the metadata behind, which is the worst
    of the three possible outcomes. It is not a half-logout an operator can
    see and retry — ``load_token`` reports no session while the metadata row
    still describes one, so status surfaces read as logged-in against a
    credential that no longer exists, and the stale row survives the retry
    because the retry finds nothing to delete.

    :meth:`~adapters.persistence.storage.SecureObjectRepository.apply_batch`
    already provides the all-or-nothing removal, and it addresses rows by the
    stored key digest, so the natural profile key is digested here through the
    same helper the write path uses.

    Args:
        profile: The profile identifier whose token and metadata records to
            delete.

    Returns:
        A pair ``(token_removed, metadata_removed)``, reporting what was
        present before the removal. Both are read before the batch rather
        than returned by it: the batch is one statement per namespace and
        reports no per-row outcome, and inferring presence from a delete's
        return value is what forced the two-commit shape to begin with.
    """
    repo = _repository()
    digest = secure_object_key_digest(profile)
    token_removed = repo.exists_by_raw_key(_NAMESPACE_TOKEN, digest)
    metadata_removed = repo.exists_by_raw_key(_NAMESPACE_METADATA, digest)
    repo.apply_batch(
        writes=(),
        deletions=(
            SecureObjectDeletion(namespace=_NAMESPACE_TOKEN, hashed_object_key=digest),
            SecureObjectDeletion(namespace=_NAMESPACE_METADATA, hashed_object_key=digest),
        ),
    )
    return token_removed, metadata_removed


__all__ = [
    "delete_session",
    "load_client",
    "load_credential_source_selection",
    "load_drive_config",
    "load_metadata",
    "load_token",
    "save_client",
    "save_credential_source_selection",
    "save_drive_config",
    "save_metadata",
    "save_token",
]


def _repository() -> SecureObjectRepository:
    return secure_object_repository_for_active_bucket()
