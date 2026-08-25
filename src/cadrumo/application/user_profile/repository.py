"""Secure-object persistence for immutable filing-time profile snapshots."""

from __future__ import annotations

from ...adapters.persistence.storage import (
    USER_PROFILE_SNAPSHOT_NAMESPACE as USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    ClassificationError,
    Envelope,
    EnvelopeVersionError,
    SecureObjectRepository,
    inner_envelope_classification_is_expected,
    inner_envelope_version_is_current,
)
from ...adapters.persistence.storage.bucket import BucketValidationError
from ...core.time import now
from ...domain.user_profile.errors import ProfileBucketMismatchError, ProfileSnapshotNotFoundError
from ...domain.user_profile.values import UserProfileSnapshot

USER_PROFILE_SNAPSHOT_NAMESPACE = USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace
_USER_PROFILE_SNAPSHOT_VERSION = USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version
_USER_PROFILE_SNAPSHOT_SENSITIVITY = USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity
_PROFILE_SNAPSHOT_MISSING_MESSAGE = "profile snapshot not found in secure storage"
_PROFILE_CLASSIFICATION_MISMATCH_MESSAGE = (
    "secure-object namespace classification does not match the repository contract"
)
_PROFILE_SNAPSHOT_VERSION_MESSAGE = "profile snapshot schema version is not supported"


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return a public secure-object repository bound to ``bucket_id``'s database.

    The storage runtime owns readiness and physical route attachment.
    User-profile repositories only name the logical bucket they need;
    the runtime verifies the active session and constructs the
    bucket-local secure-object repository.
    """
    from ...adapters.persistence.storage import secure_object_repository_for_bucket
    from ...core.config import load_settings

    return secure_object_repository_for_bucket(bucket_id, load_settings())


def user_profile_snapshot_object_key(profile_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one of a profile's filing snapshots.

    The key shape is the object-key grammar declared by
    :data:`cadrumo.adapters.persistence.storage.USER_PROFILE_SNAPSHOT_NAMESPACE`.
    A profile owns many immutable filing snapshots, so the key retains the
    ``snapshot_id`` discriminator; the first segment is the immutable
    ``profile_id`` (UUIDv4).
    """
    trimmed_profile = profile_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_profile:
        raise BucketValidationError(context={"field": "profile_id", "blank": True})
    if not trimmed_snapshot:
        raise BucketValidationError(context={"field": "snapshot_id", "blank": True})
    return f"user-profile-snapshot:{trimmed_profile}:{trimmed_snapshot}"


class _BucketBoundRepository:
    """Shared bucket-binding init for the immutable snapshot repository.

    :class:`UserProfileSnapshotRepository` binds to one bucket's own
    database (no cross-bucket reads/writes by default) and either accept
    an injected
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
    or builds one for the named bucket.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise BucketValidationError(context={"field": "bucket_id", "blank": True})
        self._bucket_id = trimmed
        # Bind to THIS bucket's own database when no repository is
        # injected — cross-bucket operations must address the named
        # bucket, not whichever profile is currently active.
        self._objects = objects or _secure_objects_for_bucket(trimmed)

    def _assert_owns(self, profile_id: str, *, surface: str) -> None:
        """Refuse a snapshot payload whose identity differs from its bucket."""
        if profile_id.strip() != self._bucket_id:
            raise ProfileBucketMismatchError(
                translated_message="application.user_profile.errors.repository_profile_bucket_mismatch",
                context={"profile_id": profile_id, "bucket_id": self._bucket_id, "surface": surface},
            )


class UserProfileSnapshotRepository(_BucketBoundRepository):
    """Read and write immutable filing-time profile snapshots in the secure DB.

    Rows use
    :data:`cadrumo.adapters.persistence.storage.USER_PROFILE_SNAPSHOT_NAMESPACE`,
    wrap each :class:`UserProfileSnapshot` in an
    :class:`~cadrumo.adapters.persistence.storage.Envelope`, and persist through
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`.
    """

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
            :class:`~cadrumo.adapters.persistence.storage.ClassificationError`:
                The envelope's classification differs from the level expected
                for snapshot data.
            :class:`~cadrumo.adapters.persistence.storage.EnvelopeVersionError`:
                The stored schema version is newer than this code can read.
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
        if not inner_envelope_classification_is_expected(envelope.classification, _USER_PROFILE_SNAPSHOT_SENSITIVITY):
            raise ClassificationError(
                _PROFILE_CLASSIFICATION_MISMATCH_MESSAGE,
                translated_message="application.user_profile.errors.repository_classification_mismatch",
                context={
                    "namespace": USER_PROFILE_SNAPSHOT_NAMESPACE,
                    "snapshot_id": snapshot_id,
                    "classification": envelope.classification.value,
                    "expected": _USER_PROFILE_SNAPSHOT_SENSITIVITY.value,
                },
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _USER_PROFILE_SNAPSHOT_VERSION):
            raise EnvelopeVersionError(
                _PROFILE_SNAPSHOT_VERSION_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_snapshot_version_unsupported",
                context={
                    "snapshot_id": snapshot_id,
                    "schema_version": envelope.schema_version,
                    "max_supported_version": _USER_PROFILE_SNAPSHOT_VERSION,
                },
            )
        if envelope.payload.profile_id != self._bucket_id:
            raise ProfileBucketMismatchError(
                translated_message="application.user_profile.errors.repository_profile_bucket_mismatch",
                context={"profile_id": envelope.payload.profile_id, "bucket_id": self._bucket_id, "surface": "load"},
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
        if snapshot.profile_id != self._bucket_id:
            raise ProfileBucketMismatchError(
                translated_message="application.user_profile.errors.repository_profile_bucket_mismatch",
                context={"profile_id": snapshot.profile_id, "bucket_id": self._bucket_id, "surface": "save"},
            )
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
    "UserProfileSnapshotRepository",
    "user_profile_snapshot_object_key",
]
