"""Secure-DB persistence for user-profile lifecycle records and filing snapshots.

Two namespaces are owned by this module:

- ``aeat.application.user_profile.value`` — live profile aggregate keyed
  by the immutable ``profile_id`` (a UUIDv4). There is exactly one live
  profile-value record per profile bucket.
- ``aeat.application.user_profile.snapshot`` — immutable filing-time
  snapshots keyed by ``(profile_id, snapshot_id)``: a profile owns many
  filing snapshots.

Both namespaces ride the active-bucket plumbing: every read and write
resolves through a profile bucket so two operators never share profile
storage. ``snapshot_id`` is deterministic in shape but globally
unique within a bucket per ``new_profile_snapshot_id``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from pydantic import ValidationError

from ...adapters.persistence.storage import (
    USER_PROFILE_SNAPSHOT_NAMESPACE as USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    USER_PROFILE_VALUE_NAMESPACE as USER_PROFILE_VALUE_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    Envelope,
)
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSnapshotNotFoundError,
    StoredProfileDriftError,
    UserProfileRecord,
    UserProfileSnapshot,
)

USER_PROFILE_VALUE_NAMESPACE = USER_PROFILE_VALUE_STORAGE_NAMESPACE.namespace
USER_PROFILE_SNAPSHOT_NAMESPACE = USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace
_USER_PROFILE_VALUE_VERSION = USER_PROFILE_VALUE_STORAGE_NAMESPACE.schema_version
_USER_PROFILE_VALUE_SENSITIVITY = USER_PROFILE_VALUE_STORAGE_NAMESPACE.sensitivity
_USER_PROFILE_SNAPSHOT_VERSION = USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version
_USER_PROFILE_SNAPSHOT_SENSITIVITY = USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return a :class:`SecureObjectRepository` bound to ``bucket_id``'s database.

    The storage runtime owns readiness and physical route attachment.
    User-profile repositories only name the logical bucket they need;
    the runtime verifies the active session and constructs the
    bucket-local secure-object repository.
    """

    from ...adapters.persistence.storage import inspect_bucket_storage_runtime
    from ...core.config import load_settings

    settings = load_settings()
    runtime = inspect_bucket_storage_runtime(
        bucket_id,
        settings,
    )
    return runtime.secure_object_repository()


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


def user_profile_value_object_key(profile_id: str) -> str:
    """Return the secure-object key for a profile's live aggregate.

    A profile bucket holds exactly one live profile-value record, so
    the key is single-segment: the immutable ``profile_id`` (UUIDv4).
    """

    trimmed_profile = profile_id.strip()
    if not trimmed_profile:
        raise ValueError("profile_id must not be blank")
    return f"user-profile:{trimmed_profile}"


def user_profile_snapshot_object_key(profile_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one of a profile's filing snapshots.

    A profile owns many immutable filing snapshots, so the key retains
    the ``snapshot_id`` discriminator; the first segment is the
    immutable ``profile_id`` (UUIDv4).
    """

    trimmed_profile = profile_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_profile:
        raise ValueError("profile_id must not be blank")
    if not trimmed_snapshot:
        raise ValueError("snapshot_id must not be blank")
    return f"user-profile-snapshot:{trimmed_profile}:{trimmed_snapshot}"


class UserProfileLifecycleRepository:
    """Read and write live user-profile aggregates in the secure DB."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise ValueError("bucket_id must not be blank")
        # Bind to THIS bucket's own database when no repository is
        # injected — cross-bucket operations must address the named
        # bucket, not whichever profile is currently active.
        self._objects = objects or _secure_objects_for_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, profile_id: str) -> bool:
        return self._objects.exists(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(profile_id),
        )

    def load(self, profile_id: str) -> UserProfileRecord:
        record = self._objects.load(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(profile_id),
            expected_class=_USER_PROFILE_VALUE_SENSITIVITY,
            max_supported_version=_USER_PROFILE_VALUE_VERSION,
        )
        if record is None:
            raise ProfileNotFoundError(f"profile {profile_id!r} not found in bucket {self._bucket_id!r}")
        try:
            envelope = Envelope[UserProfileRecord].model_validate_json(record.payload.decode("utf-8"))
        except ValidationError as exc:
            raise StoredProfileDriftError(profile_id, exc) from exc
        if envelope.classification is not _USER_PROFILE_VALUE_SENSITIVITY:
            raise ClassificationError(
                f"profile {profile_id!r} has classification {envelope.classification}; "
                f"consumer expected {_USER_PROFILE_VALUE_SENSITIVITY}",
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
            classification=_USER_PROFILE_VALUE_SENSITIVITY,
            payload=record,
        )
        self._objects.save(
            namespace=USER_PROFILE_VALUE_NAMESPACE,
            object_key=user_profile_value_object_key(record.profile_id),
            classification=_USER_PROFILE_VALUE_SENSITIVITY,
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
            expected_class=_USER_PROFILE_VALUE_SENSITIVITY,
            max_supported_version=_USER_PROFILE_VALUE_VERSION,
        ):
            # Extract the profile_id from the hashed object key is not
            # possible (keys are stored hashed); use the bucket_id as
            # the context identifier so the error is still actionable.
            try:
                envelope = Envelope[UserProfileRecord].model_validate_json(raw.payload.decode("utf-8"))
            except ValidationError as exc:
                raise StoredProfileDriftError(self._bucket_id, exc) from exc
            yield envelope.payload

    def delete(self, profile_id: str) -> bool:
        deleted = self._objects.delete(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(profile_id),
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
        # Bind to THIS bucket's own database when no repository is
        # injected — cross-bucket operations must address the named
        # bucket, not whichever profile is currently active.
        self._objects = objects or _secure_objects_for_bucket(self._bucket_id)

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
            expected_class=_USER_PROFILE_SNAPSHOT_SENSITIVITY,
            max_supported_version=_USER_PROFILE_SNAPSHOT_VERSION,
        )
        if record is None:
            raise ProfileSnapshotNotFoundError(f"snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}")
        envelope = Envelope[UserProfileSnapshot].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not _USER_PROFILE_SNAPSHOT_SENSITIVITY:
            raise ClassificationError(
                f"snapshot {snapshot_id!r} has classification {envelope.classification}; "
                f"consumer expected {_USER_PROFILE_SNAPSHOT_SENSITIVITY}",
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
            classification=_USER_PROFILE_SNAPSHOT_SENSITIVITY,
            payload=snapshot,
        )
        self._objects.save(
            namespace=USER_PROFILE_SNAPSHOT_NAMESPACE,
            object_key=user_profile_snapshot_object_key(self._bucket_id, snapshot.snapshot_id),
            classification=_USER_PROFILE_SNAPSHOT_SENSITIVITY,
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
