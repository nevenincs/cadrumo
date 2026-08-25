"""Secure-object persistence for immutable filing-time profile snapshots."""

from __future__ import annotations

from ...core.time import now
from ...domain.user_profile.errors import (
    ProfileBucketMismatchError,
    ProfileSnapshotClassificationError,
    ProfileSnapshotNotFoundError,
    ProfileSnapshotVersionError,
    UserProfileValidationError,
)
from ...domain.user_profile.values import UserProfileSnapshot
from .custody_ports import (
    ProfileCustodySecureObjectRepositoryPort,
    ProfileSnapshotPersistencePort,
    profile_custody_port,
)

_PROFILE_SNAPSHOT_MISSING_MESSAGE = "profile snapshot not found in secure storage"
_PROFILE_CLASSIFICATION_MISMATCH_MESSAGE = (
    "secure-object namespace classification does not match the repository contract"
)
_PROFILE_SNAPSHOT_VERSION_MESSAGE = "profile snapshot schema version is not supported"


def user_profile_snapshot_object_key(profile_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one of a profile's filing snapshots.

    A profile owns many immutable filing snapshots, so the key retains the
    ``snapshot_id`` discriminator; the first segment is the immutable
    ``profile_id`` (UUIDv4).
    """
    trimmed_profile = profile_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_profile:
        raise UserProfileValidationError(context={"field": "profile_id", "blank": True})
    if not trimmed_snapshot:
        raise UserProfileValidationError(context={"field": "snapshot_id", "blank": True})
    return f"user-profile-snapshot:{trimmed_profile}:{trimmed_snapshot}"


class _BucketBoundRepository:
    """Shared bucket-binding init for the immutable snapshot repository.

    :class:`UserProfileSnapshotRepository` binds to one bucket's own database
    (no cross-bucket reads/writes by default) and either accepts an injected
    secure-object port or resolves the composed snapshot persistence port.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        objects: ProfileCustodySecureObjectRepositoryPort | None = None,
    ) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise UserProfileValidationError(context={"field": "bucket_id", "blank": True})
        self._bucket_id = trimmed
        # Bind to THIS bucket's own database when no repository is
        # injected — cross-bucket operations must address the named
        # bucket, not whichever profile is currently active.
        self._persistence: ProfileSnapshotPersistencePort = profile_custody_port().profile_snapshot_persistence(
            trimmed,
            objects=objects,
        )

    def _assert_owns(self, profile_id: str, *, surface: str) -> None:
        """Refuse a snapshot payload whose identity differs from its bucket."""
        if profile_id.strip() != self._bucket_id:
            raise ProfileBucketMismatchError(
                translated_message="application.user_profile.errors.repository_profile_bucket_mismatch",
                context={"profile_id": profile_id, "bucket_id": self._bucket_id, "surface": surface},
            )


class UserProfileSnapshotRepository(_BucketBoundRepository):
    """Read and write immutable filing-time profile snapshots in the secure DB.

    Persistence-specific namespace registration, envelope encoding, and secure
    storage live behind the composed profile-snapshot port.
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
        return self._persistence.exists(user_profile_snapshot_object_key(self._bucket_id, snapshot_id))

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
        record = self._persistence.load(user_profile_snapshot_object_key(self._bucket_id, snapshot_id))
        if record is None:
            raise ProfileSnapshotNotFoundError(
                _PROFILE_SNAPSHOT_MISSING_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_snapshot_missing",
                context={"snapshot_id": snapshot_id, "bucket_id": self._bucket_id},
            )
        if record.classification is not self._persistence.sensitivity:
            raise ProfileSnapshotClassificationError(
                _PROFILE_CLASSIFICATION_MISMATCH_MESSAGE,
                translated_message="application.user_profile.errors.repository_classification_mismatch",
                context={
                    "namespace": self._persistence.namespace,
                    "snapshot_id": snapshot_id,
                    "classification": record.classification.value,
                    "expected": self._persistence.sensitivity.value,
                },
            )
        if record.schema_version != self._persistence.schema_version:
            raise ProfileSnapshotVersionError(
                _PROFILE_SNAPSHOT_VERSION_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_snapshot_version_unsupported",
                context={
                    "snapshot_id": snapshot_id,
                    "schema_version": record.schema_version,
                    "max_supported_version": self._persistence.schema_version,
                },
            )
        if record.snapshot.profile_id != self._bucket_id:
            raise ProfileBucketMismatchError(
                translated_message="application.user_profile.errors.repository_profile_bucket_mismatch",
                context={"profile_id": record.snapshot.profile_id, "bucket_id": self._bucket_id, "surface": "load"},
            )
        return record.snapshot

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
        self._persistence.save(
            user_profile_snapshot_object_key(self._bucket_id, snapshot.snapshot_id),
            snapshot,
            written_at=now(),
        )


__all__ = [
    "UserProfileSnapshotRepository",
    "user_profile_snapshot_object_key",
]
