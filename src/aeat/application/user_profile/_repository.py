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
unique within a bucket per ``new_profile_snapshot_id``. Records are
stored as :class:`Envelope` objects encrypted at rest.
"""

from __future__ import annotations

from collections.abc import Iterable

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
from ...adapters.persistence.storage.bucket import BucketValidationError
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ...core.time import now
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
_PROFILE_RECORD_MISSING_MESSAGE = "profile record not found in secure storage"
_PROFILE_RECORD_CLASSIFICATION_MESSAGE = "profile record classification is incompatible with this repository"
_PROFILE_RECORD_VERSION_MESSAGE = "profile record schema version is not supported"
_PROFILE_SNAPSHOT_MISSING_MESSAGE = "profile snapshot not found in secure storage"
_PROFILE_SNAPSHOT_CLASSIFICATION_MESSAGE = "profile snapshot classification is incompatible with this repository"
_PROFILE_SNAPSHOT_VERSION_MESSAGE = "profile snapshot schema version is not supported"
_log = get_logger(__name__)


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return a :class:`SecureObjectRepository` bound to ``bucket_id``'s database.

    The storage runtime owns readiness and physical route attachment.
    User-profile repositories only name the logical bucket they need;
    the runtime verifies the active session and constructs the
    bucket-local secure-object repository.
    """
    from ...adapters.persistence.storage import secure_object_repository_for_bucket
    from ...core.config import load_settings

    return secure_object_repository_for_bucket(bucket_id, load_settings())


def _clear_output_language_cache() -> None:
    """Invalidate cached i18n output-language resolution after a profile write.

    Every persisted profile fact write may shift the active profile's
    ``preferences.output_language`` and therefore the resolved CLI render
    language. Importing lazily so persistence cannot block on the i18n
    module.
    """
    try:
        from ...core.i18n._render import clear_output_language_cache
    except ImportError:  # pragma: no cover - cache invalidation must never block persistence
        _log.debug("user-profile output-language cache invalidation import failed", exc_info=True)
        return
    clear_output_language_cache()


def user_profile_value_object_key(profile_id: str) -> str:
    """Return the secure-object key for a profile's live aggregate.

    A profile bucket holds exactly one live profile-value record, so
    the key is single-segment: the immutable ``profile_id`` (UUIDv4).
    """
    trimmed_profile = profile_id.strip()
    if not trimmed_profile:
        raise BucketValidationError("profile_id must not be blank")
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
        raise BucketValidationError("profile_id must not be blank")
    if not trimmed_snapshot:
        raise BucketValidationError("snapshot_id must not be blank")
    return f"user-profile-snapshot:{trimmed_profile}:{trimmed_snapshot}"


class _BucketBoundRepository:
    """Shared bucket-binding init for the user-profile repository pair.

    Both :class:`UserProfileLifecycleRepository` and
    :class:`UserProfileSnapshotRepository` bind to one bucket's own
    database (no cross-bucket reads/writes by default) and either accept
    an injected :class:`SecureObjectRepository` or build one for the
    named bucket. The constructor is identical across both classes so it
    lives here as a single source of truth.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise BucketValidationError("bucket_id must not be blank")
        self._bucket_id = trimmed
        # Bind to THIS bucket's own database when no repository is
        # injected — cross-bucket operations must address the named
        # bucket, not whichever profile is currently active.
        self._objects = objects or _secure_objects_for_bucket(trimmed)


class UserProfileLifecycleRepository(_BucketBoundRepository):
    """Read and write live user-profile aggregates in the secure DB."""

    @property
    def bucket_id(self) -> str:
        """Return the logical profile bucket this repository is bound to.

        A bucket is a named, isolated storage partition: every read and write
        addresses this bucket's own database, so two operators never share
        profile storage. The value is the stripped, non-blank identifier
        supplied at construction.

        Returns:
            The name of the bucket (storage partition) this repository
            operates against.
        """
        return self._bucket_id

    def exists(self, profile_id: str) -> bool:
        """Report whether a live profile aggregate is stored under ``profile_id``.

        Probes the secure-object backend for the single live profile-value
        record keyed by ``profile_id`` (a UUIDv4) in this bucket, without
        decrypting or validating the payload.

        Args:
            profile_id: The immutable UUIDv4 identifying the profile.

        Returns:
            ``True`` when a record exists under that key, else ``False``.
        """
        return self._objects.exists(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(profile_id),
        )

    def load(self, profile_id: str) -> UserProfileRecord:
        """Load and decrypt the live profile aggregate for ``profile_id``.

        Reads the encrypted ``Envelope`` (the stored container that holds the
        encrypted payload plus its metadata) for the single live profile
        record in this bucket, validates it back into a :class:`UserProfileRecord`,
        and enforces two storage-contract checks before returning the payload.
        First, the envelope's classification (its declared sensitivity level)
        must match the level expected for profile data. Second, the schema
        version recorded on the envelope must not be newer than the version
        this code can read.

        Args:
            profile_id: The immutable UUIDv4 identifying the profile.

        Returns:
            The decrypted :class:`UserProfileRecord` carried by the envelope.

        Raises:
            ProfileNotFoundError: No record is stored under ``profile_id``
                in this bucket.
            StoredProfileDriftError: The stored payload no longer validates
                against the current ``UserProfileRecord`` schema.
            ClassificationError: The envelope's classification differs from
                the level expected for profile data.
            EnvelopeVersionError: The stored schema version is newer than
                this code can read.
        """
        record = self._objects.load(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(profile_id),
            expected_class=_USER_PROFILE_VALUE_SENSITIVITY,
            max_supported_version=_USER_PROFILE_VALUE_VERSION,
        )
        if record is None:
            raise ProfileNotFoundError(
                _PROFILE_RECORD_MISSING_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_record_missing",
                context={"profile_id": profile_id, "bucket_id": self._bucket_id},
            )
        try:
            envelope = Envelope[UserProfileRecord].model_validate_json(record.payload.decode("utf-8"))
        except ValidationError as exc:
            raise StoredProfileDriftError(profile_id, exc) from exc
        if envelope.classification is not _USER_PROFILE_VALUE_SENSITIVITY:
            raise ClassificationError(
                _PROFILE_RECORD_CLASSIFICATION_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_record_classification_mismatch",
                context={
                    "profile_id": profile_id,
                    "classification": envelope.classification.value,
                    "expected": _USER_PROFILE_VALUE_SENSITIVITY.value,
                },
            )
        if envelope.schema_version > _USER_PROFILE_VALUE_VERSION:
            raise EnvelopeVersionError(
                _PROFILE_RECORD_VERSION_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_record_version_unsupported",
                context={
                    "profile_id": profile_id,
                    "schema_version": envelope.schema_version,
                    "max_supported_version": _USER_PROFILE_VALUE_VERSION,
                },
            )
        return envelope.payload

    def save(self, record: UserProfileRecord) -> None:
        """Persist ``record`` as this bucket's single live profile aggregate.

        Wraps the :class:`UserProfileRecord` in an encrypted ``Envelope`` (the
        stored container holding the encrypted payload plus its metadata)
        stamped with the current schema version, the write timestamp, and the
        sensitivity classification for profile data, then stores it under the
        key derived from ``record.profile_id``. A profile bucket holds exactly
        one live profile record, so this overwrites any prior aggregate for
        the same ``profile_id``. Afterwards it clears the cached output
        language, because a write may have changed the active profile's
        preferred language for command-line output.

        Args:
            record: The live :class:`UserProfileRecord` aggregate to encrypt and store.
        """
        envelope = Envelope[UserProfileRecord](
            schema_version=_USER_PROFILE_VALUE_VERSION,
            written_at=now(),
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
        """Remove the live profile aggregate stored under ``profile_id``.

        Deletes the single live profile record keyed by ``profile_id`` from
        this bucket. When a record was actually removed, it clears the cached
        output language, because the deleted profile may have governed the
        active profile's preferred language for command-line output.

        Args:
            profile_id: The immutable UUIDv4 identifying the profile.

        Returns:
            ``True`` when a record was deleted, ``False`` when no record was
            stored under that key.
        """
        deleted = self._objects.delete(
            USER_PROFILE_VALUE_NAMESPACE,
            user_profile_value_object_key(profile_id),
        )
        if deleted:
            _clear_output_language_cache()
        return deleted


class UserProfileSnapshotRepository(_BucketBoundRepository):
    """Read and write immutable filing-time profile snapshots in the secure DB."""

    @property
    def bucket_id(self) -> str:
        """Return the logical profile bucket this repository is bound to.

        A bucket is a named, isolated storage partition: snapshot keys are
        scoped to this bucket, so every read and write addresses the bucket's
        own database and no two operators share snapshot storage. The value is
        the stripped, non-blank identifier supplied at construction.

        Returns:
            The name of the bucket (storage partition) this repository
            operates against.
        """
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        """Report whether a filing-time snapshot is stored under ``snapshot_id``.

        Probes the secure-object backend for the immutable snapshot keyed by
        this bucket and ``snapshot_id``, without decrypting or validating the
        payload. A snapshot is the frozen profile state captured at the
        moment a tax filing was prepared; a profile owns many such snapshots.

        Args:
            snapshot_id: The identifier of the snapshot, globally unique
                within this bucket.

        Returns:
            ``True`` when a snapshot exists under that key, else ``False``.
        """
        return self._objects.exists(
            USER_PROFILE_SNAPSHOT_NAMESPACE,
            user_profile_snapshot_object_key(self._bucket_id, snapshot_id),
        )

    def load(self, snapshot_id: str) -> UserProfileSnapshot:
        """Load and decrypt the filing-time snapshot for ``snapshot_id``.

        A snapshot is the frozen profile state captured when a tax filing was
        prepared. Reads the encrypted ``Envelope`` (the stored container that
        holds the encrypted payload plus its metadata) for the immutable
        snapshot keyed by this bucket and ``snapshot_id``, validates it into a
        :class:`UserProfileSnapshot`, and enforces two storage-contract checks
        before returning the payload. First, the envelope's classification
        (its declared sensitivity level) must match the level expected for
        snapshot data. Second, the schema version recorded on the envelope
        must not be newer than the version this code can read.

        Args:
            snapshot_id: The identifier of the snapshot, globally unique
                within this bucket.

        Returns:
            The decrypted :class:`UserProfileSnapshot` carried by the envelope.

        Raises:
            ProfileSnapshotNotFoundError: No snapshot is stored under
                ``snapshot_id`` in this bucket.
            ClassificationError: The envelope's classification differs from
                the level expected for snapshot data.
            EnvelopeVersionError: The stored schema version is newer than
                this code can read.
        """
        record = self._objects.load(
            USER_PROFILE_SNAPSHOT_NAMESPACE,
            user_profile_snapshot_object_key(self._bucket_id, snapshot_id),
            expected_class=_USER_PROFILE_SNAPSHOT_SENSITIVITY,
            max_supported_version=_USER_PROFILE_SNAPSHOT_VERSION,
        )
        if record is None:
            raise ProfileSnapshotNotFoundError(
                _PROFILE_SNAPSHOT_MISSING_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_snapshot_missing",
                context={"snapshot_id": snapshot_id, "bucket_id": self._bucket_id},
            )
        envelope = Envelope[UserProfileSnapshot].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not _USER_PROFILE_SNAPSHOT_SENSITIVITY:
            raise ClassificationError(
                _PROFILE_SNAPSHOT_CLASSIFICATION_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_snapshot_classification_mismatch",
                context={
                    "snapshot_id": snapshot_id,
                    "classification": envelope.classification.value,
                    "expected": _USER_PROFILE_SNAPSHOT_SENSITIVITY.value,
                },
            )
        if envelope.schema_version > _USER_PROFILE_SNAPSHOT_VERSION:
            raise EnvelopeVersionError(
                _PROFILE_SNAPSHOT_VERSION_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_snapshot_version_unsupported",
                context={
                    "snapshot_id": snapshot_id,
                    "schema_version": envelope.schema_version,
                    "max_supported_version": _USER_PROFILE_SNAPSHOT_VERSION,
                },
            )
        return envelope.payload

    def save(self, snapshot: UserProfileSnapshot) -> None:
        """Persist ``snapshot`` as an immutable filing-time snapshot.

        A snapshot is the frozen profile state captured when a tax filing was
        prepared. Wraps the ``UserProfileSnapshot`` in an encrypted
        ``Envelope`` (the stored container holding the encrypted payload plus
        its metadata) stamped with the current schema version, the write
        timestamp, and the sensitivity classification for snapshot data, then
        stores it under the key derived from this bucket and
        ``snapshot.snapshot_id``. Snapshots never change once written, so each
        save adds a new entry to the many snapshots a profile owns rather than
        mutating live profile state.

        Args:
            snapshot: The filing-time profile snapshot to encrypt and store.
        """
        envelope = Envelope[UserProfileSnapshot](
            schema_version=_USER_PROFILE_SNAPSHOT_VERSION,
            written_at=now(),
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
