"""Secure-DB persistence for user-profile lifecycle records and filing snapshots.

Two namespaces are owned by this module:

- ``aeat.application.user_profile.value`` — live profile aggregate per
  ``(bucket_id, profile_id)``.
- ``aeat.application.user_profile.snapshot`` — immutable filing-time
  snapshots per ``(bucket_id, snapshot_id)``.

Both namespaces ride the active-bucket plumbing: every read and write
resolves through a profile bucket so two operators never share profile
storage. ``snapshot_id`` is deterministic in shape but globally
unique within a bucket per ``new_profile_snapshot_id``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSnapshotNotFoundError,
    UserProfileRecord,
    UserProfileSnapshot,
)

USER_PROFILE_VALUE_NAMESPACE = "aeat.application.user_profile.value"
USER_PROFILE_SNAPSHOT_NAMESPACE = "aeat.application.user_profile.snapshot"
_USER_PROFILE_VALUE_VERSION = 1
_USER_PROFILE_SNAPSHOT_VERSION = 1


def _clear_output_language_cache() -> None:
    """Invalidate cached i18n output-language resolution after a profile write.

    Every persisted profile fact write may shift the active profile's
    ``preferences.output_language`` and therefore the resolved CLI render
    language. Importing lazily so persistence cannot block on the i18n
    module.
    """

    try:
        from ...core.i18n._render import clear_output_language_cache
    except Exception:  # pragma: no cover - cache invalidation must never block persistence
        return
    clear_output_language_cache()


def user_profile_value_object_key(bucket_id: str, profile_id: str) -> str:
    """Return the secure-object key for one bucket's profile aggregate."""

    trimmed_bucket = bucket_id.strip()
    trimmed_profile = profile_id.strip()
    if not trimmed_bucket:
        raise ValueError("bucket_id must not be blank")
    if not trimmed_profile:
        raise ValueError("profile_id must not be blank")
    return f"user-profile:{trimmed_bucket}:{trimmed_profile}"


def user_profile_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one bucket's filing-time snapshot."""

    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise ValueError("bucket_id must not be blank")
    if not trimmed_snapshot:
        raise ValueError("snapshot_id must not be blank")
    return f"user-profile-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


class UserProfileLifecycleRepository:
    """Read and write live user-profile aggregates in the secure DB."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise ValueError("bucket_id must not be blank")
        self._objects = objects or SecureObjectRepository()

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, profile_id: str) -> bool:
        return self._objects.exists(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(self._bucket_id, profile_id),
        )

    def load(self, profile_id: str) -> UserProfileRecord:
        record = self._objects.load(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(self._bucket_id, profile_id),
            expected_class=SensitivityClass.IDENTITY,
            max_supported_version=_USER_PROFILE_VALUE_VERSION,
        )
        if record is None:
            raise ProfileNotFoundError(f"profile {profile_id!r} not found in bucket {self._bucket_id!r}")
        envelope = Envelope[UserProfileRecord].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.IDENTITY:
            raise ClassificationError(
                f"profile {profile_id!r} has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.IDENTITY}",
            )
        if envelope.schema_version > _USER_PROFILE_VALUE_VERSION:
            raise EnvelopeVersionError(
                f"profile {profile_id!r} is at version {envelope.schema_version}; "
                f"consumer supports up to {_USER_PROFILE_VALUE_VERSION}",
            )
        return envelope.payload

    def save(self, record: UserProfileRecord) -> None:
        envelope = Envelope[UserProfileRecord](
            schema_version=_USER_PROFILE_VALUE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.IDENTITY,
            payload=record,
        )
        self._objects.save(
            namespace=USER_PROFILE_VALUE_NAMESPACE,
            object_key=user_profile_value_object_key(self._bucket_id, record.profile_id),
            classification=SensitivityClass.IDENTITY,
            schema_version=_USER_PROFILE_VALUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _clear_output_language_cache()

    def iter_records(self) -> Iterable[UserProfileRecord]:
        """Yield every live :class:`UserProfileRecord` from the secure-object backend.

        Walks the IDENTITY-class secure-object index for this bucket
        namespace and validates each row against the typed envelope at
        the configured schema version. The lifecycle service consumes
        this iterator to list live profiles without reaching for the
        repository's private secure-object reference.
        """

        for raw in self._objects.list_records(
            USER_PROFILE_VALUE_NAMESPACE,
            expected_class=SensitivityClass.IDENTITY,
            max_supported_version=_USER_PROFILE_VALUE_VERSION,
        ):
            envelope = Envelope[UserProfileRecord].model_validate_json(raw.payload.decode("utf-8"))
            yield envelope.payload

    def delete(self, profile_id: str) -> bool:
        deleted = self._objects.delete(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(self._bucket_id, profile_id),
        )
        if deleted:
            _clear_output_language_cache()
        return deleted


class UserProfileSnapshotRepository:
    """Read and write immutable filing-time profile snapshots in the secure DB."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise ValueError("bucket_id must not be blank")
        self._objects = objects or SecureObjectRepository()

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._objects.exists(
            USER_PROFILE_SNAPSHOT_NAMESPACE,
            user_profile_snapshot_object_key(self._bucket_id, snapshot_id),
        )

    def load(self, snapshot_id: str) -> UserProfileSnapshot:
        record = self._objects.load(
            USER_PROFILE_SNAPSHOT_NAMESPACE,
            user_profile_snapshot_object_key(self._bucket_id, snapshot_id),
            expected_class=SensitivityClass.IDENTITY,
            max_supported_version=_USER_PROFILE_SNAPSHOT_VERSION,
        )
        if record is None:
            raise ProfileSnapshotNotFoundError(f"snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}")
        envelope = Envelope[UserProfileSnapshot].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.IDENTITY:
            raise ClassificationError(
                f"snapshot {snapshot_id!r} has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.IDENTITY}",
            )
        if envelope.schema_version > _USER_PROFILE_SNAPSHOT_VERSION:
            raise EnvelopeVersionError(
                f"snapshot {snapshot_id!r} is at version {envelope.schema_version}; "
                f"consumer supports up to {_USER_PROFILE_SNAPSHOT_VERSION}",
            )
        return envelope.payload

    def save(self, snapshot: UserProfileSnapshot) -> None:
        envelope = Envelope[UserProfileSnapshot](
            schema_version=_USER_PROFILE_SNAPSHOT_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.IDENTITY,
            payload=snapshot,
        )
        self._objects.save(
            namespace=USER_PROFILE_SNAPSHOT_NAMESPACE,
            object_key=user_profile_snapshot_object_key(self._bucket_id, snapshot.snapshot_id),
            classification=SensitivityClass.IDENTITY,
            schema_version=_USER_PROFILE_SNAPSHOT_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


__all__ = [
    "USER_PROFILE_SNAPSHOT_NAMESPACE",
    "USER_PROFILE_VALUE_NAMESPACE",
    "UserProfileLifecycleRepository",
    "UserProfileSnapshotRepository",
    "user_profile_snapshot_object_key",
    "user_profile_value_object_key",
]
