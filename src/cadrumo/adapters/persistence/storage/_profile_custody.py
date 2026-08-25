"""Concrete persistence adapter for the application profile-custody port."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, NoReturn
from uuid import UUID

from ....application.user_profile.authentication import ProfilePasswordProofOperation
from ....application.user_profile.custody_ports import (
    ProfileBucketStoragePathsPort,
    ProfileBucketStoragePort,
    ProfileCapsuleArchiveContentsMaterial,
    ProfileCapsuleArchiveHeaderMaterial,
    ProfileCustodyBucketEventHistoryPort,
    ProfileCustodyCapsuleLabelPort,
    ProfileCustodyCapsuleSourceMaterial,
    ProfileCustodyCarryMaterial,
    ProfileCustodyEnvelopePort,
    ProfileCustodyInventoryPort,
    ProfileCustodyLabelHeadPort,
    ProfileCustodyLocalRecordStore,
    ProfileCustodyPasswordMaterialPort,
    ProfileCustodyPasswordProofMaterialPort,
    ProfileCustodyPort,
    ProfileCustodyRecordIntegrityError,
    ProfileCustodyRecoveryArtifactExportReceiptPort,
    ProfileCustodyRecoveryEnrollmentMaterial,
    ProfileCustodyRecoveryEnvelopePort,
    ProfileCustodyRecoveryUnlockPort,
    ProfileCustodyRegistrationMaterial,
    ProfileCustodySecureObjectNamespace,
    ProfileCustodySecureObjectRepositoryPort,
    ProfileCustodySentinelPort,
    ProfileCustodyUnlockPort,
    ProfilePassphraseEncryptedRecord,
    ProfilePassphraseKdfParameters,
    ProfilePassphraseKdfPolicy,
    ProfileRecordCryptoError,
    ProfileRecordCryptoPort,
    ProfileRecordEncryptedBlob,
    ProfileSecureObjectInventoryPort,
    ProfileSnapshotPersistencePort,
)
from ....core import StorageCategory, StorageCustodyProfile, storage_location
from ....core.classification import SensitivityClass
from ....core.config import Settings
from ....core.hashing import prefixed_digest
from ....core.time import now as _utc_now
from ....domain.user_profile.errors import (
    PROFILE_SNAPSHOT_CLASSIFICATION_MISMATCH_MESSAGE,
    PROFILE_SNAPSHOT_VERSION_UNSUPPORTED_MESSAGE,
    ProfileSnapshotClassificationError,
    ProfileSnapshotNotFoundError,
    ProfileSnapshotVersionError,
    UserProfileValidationError,
)
from ....domain.user_profile.portable_export import CarriedSecureObject
from ....domain.user_profile.values import UserProfileSnapshot
from ..profile.buckets import BucketEventHistoryRepository
from ..profile.snapshots import SecureSnapshotRepository
from . import (
    USER_PROFILE_SNAPSHOT_NAMESPACE,
    USER_PROFILE_VALUE_NAMESPACE,
    ClassificationError,
    EnvelopeVersionError,
    KeyringUnavailableError,
    MasterKeyMaterialMissingError,
    PersistenceError,
    SecureObjectRepository,
    bucket,
    crypto,
    custody,
    generate_recovery_key,
    master_key,
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_bucket,
    secure_object_repository_for_staged_bucket,
)
from ._kdf_salt import KDF_SALT_BYTES
from ._profile_custody_carry import (
    collect_profile_custody_carry as _collect_profile_custody_carry,
)
from ._profile_custody_carry import (
    restore_profile_custody_carry as _restore_profile_custody_carry,
)


def _capsule_relative(category: StorageCategory) -> Path:
    """Return the capsule-relative subpath the storage taxonomy declares for ``category``.

    A capsule is read from a supplied source directory rather than the operator's
    storage root, so these are joined onto that source -- but the subpath itself is
    still the taxonomy's to declare, not this module's to spell.
    """
    return storage_location(category).relative_path()


def _recovery_artifact_receipt(value: object) -> ProfileCustodyRecoveryArtifactExportReceiptPort:
    if not isinstance(value, ProfileCustodyRecoveryArtifactExportReceiptPort):
        raise TypeError("recovery artifact receipt does not satisfy the application custody boundary")
    return value


def _substrate_handle[T](value: object, expected: type[T], subject: str) -> T:
    if not isinstance(value, expected):
        raise TypeError(f"{subject} did not originate from the custody substrate: {type(value).__name__}")
    return value


class _PersistenceProfileCustodyLocalRecordStore:
    def ensure_directory(self, path: Path) -> None:
        custody.ensure_profile_custody_local_directory(path)

    def lock(self, path: Path, *, timeout_seconds: float = 30.0) -> AbstractContextManager[None]:
        return custody.profile_custody_local_lock(path, timeout_seconds=timeout_seconds)

    def root_lock(self, root: Path, *, timeout_seconds: float = 30.0) -> AbstractContextManager[None]:
        return custody.profile_custody_root_lock(root, timeout_seconds=timeout_seconds)

    def read(self, path: Path, *, maximum_bytes: int) -> bytes:
        return custody.read_profile_custody_local_record(path, maximum_bytes=maximum_bytes)

    def read_optional(self, path: Path, *, maximum_bytes: int) -> bytes | None:
        return custody.read_optional_profile_custody_local_record(path, maximum_bytes=maximum_bytes)

    def write(self, path: Path, payload: bytes, *, publish_once: bool) -> None:
        custody.write_profile_custody_local_record(path, payload, publish_once=publish_once)

    def clear(self, path: Path) -> None:
        custody.clear_profile_custody_local_record(path)

    def compare_and_replace(
        self,
        path: Path,
        *,
        expected: bytes | None,
        replacement: bytes,
        maximum_bytes: int,
    ) -> None:
        custody.compare_and_replace_profile_custody_local_record(
            path,
            expected=expected,
            replacement=replacement,
            maximum_bytes=maximum_bytes,
        )

    def compare_and_replace_same_or_predecessor(
        self,
        path: Path,
        *,
        current: bytes,
        predecessor: bytes | None,
        maximum_bytes: int,
    ) -> None:
        custody.compare_and_replace_same_or_predecessor_profile_custody_local_record(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=maximum_bytes,
        )

    def compare_and_clear(self, path: Path, *, expected: bytes, maximum_bytes: int) -> None:
        custody.compare_and_clear_profile_custody_local_record(path, expected=expected, maximum_bytes=maximum_bytes)


class _PersistenceProfileBucketStorage:
    def resolve(self, root: Path, bucket_id: str) -> ProfileBucketStoragePathsPort:
        return bucket.bucket_paths(root, bucket_id)

    def acquire_lock(self, paths: ProfileBucketStoragePathsPort, *, wait_seconds: float) -> None:
        bucket.acquire_lock(paths, wait_seconds=wait_seconds)

    def release_lock(self, paths: ProfileBucketStoragePathsPort) -> None:
        bucket.release_lock(paths)


class _PersistenceProfileSecureObjectInventory:
    def __init__(self) -> None:
        repository = secure_object_repository_for_active_bucket()
        self._list_namespaces = repository.list_namespaces
        self._list_keys = repository.list_keys

    def list_namespaces(self) -> tuple[str, ...]:
        return self._list_namespaces()

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        return self._list_keys(namespace)


class _PersistenceProfileSnapshotStore:
    """Profile port over the canonical generic snapshot persistence adapter."""

    def __init__(
        self,
        *,
        bucket_id: str,
        object_key: Callable[[str, str], str],
        objects: SecureObjectRepository | None,
    ) -> None:
        def not_found(snapshot_id: str) -> Exception:
            return ProfileSnapshotNotFoundError(context={"snapshot_id": snapshot_id})

        def ambiguous(prefix: str, matches: tuple[str, ...]) -> Exception:
            return UserProfileValidationError(context={"snapshot_id_prefix": prefix, "matches": matches})

        def classification_error(
            snapshot_id: str,
            actual: SensitivityClass,
            expected: SensitivityClass,
        ) -> Exception:
            return ProfileSnapshotClassificationError(
                PROFILE_SNAPSHOT_CLASSIFICATION_MISMATCH_MESSAGE,
                translated_message="application.user_profile.errors.repository_classification_mismatch",
                context={
                    "namespace": USER_PROFILE_SNAPSHOT_NAMESPACE.namespace,
                    "snapshot_id": snapshot_id,
                    "classification": actual.value,
                    "expected": expected.value,
                },
            )

        def version_error(snapshot_id: str, actual: int, expected: int) -> Exception:
            return ProfileSnapshotVersionError(
                PROFILE_SNAPSHOT_VERSION_UNSUPPORTED_MESSAGE,
                translated_message="application.user_profile.errors.repository_profile_snapshot_version_unsupported",
                context={
                    "snapshot_id": snapshot_id,
                    "schema_version": actual,
                    "max_supported_version": expected,
                },
            )

        self._delegate = SecureSnapshotRepository(
            bucket_id=bucket_id,
            payload_model=UserProfileSnapshot,
            namespace_definition=USER_PROFILE_SNAPSHOT_NAMESPACE,
            object_key=object_key,
            not_found_factory=not_found,
            ambiguous_prefix_factory=ambiguous,
            domain_label="profile",
            input_error_cls=UserProfileValidationError,
            objects=objects,
            enforce_payload_identity=False,
            classification_error_factory=classification_error,
            version_error_factory=version_error,
        )

    def exists(self, snapshot_id: str) -> bool:
        return self._delegate.exists(snapshot_id)

    def load(self, snapshot_id: str) -> UserProfileSnapshot | None:
        try:
            return self._delegate.load(snapshot_id)
        except ProfileSnapshotNotFoundError:
            return None
        except ClassificationError as exc:
            raise ProfileSnapshotClassificationError(
                str(exc),
                translated_message=exc.translated_message,
                context=exc.context,
            ) from exc
        except EnvelopeVersionError as exc:
            raise ProfileSnapshotVersionError(
                str(exc),
                translated_message=exc.translated_message,
                context=exc.context,
            ) from exc

    def save(self, snapshot: UserProfileSnapshot) -> None:
        self._delegate.save(snapshot)


class _PersistenceProfileRecordCrypto:
    def passphrase_kdf_policy(self) -> ProfilePassphraseKdfPolicy:
        return ProfilePassphraseKdfPolicy(
            version=master_key.ARGON2_VERSION,
            minimum_memory_cost_kib=master_key.MIN_MEMORY_COST_KIB,
            maximum_memory_cost_kib=master_key.MAX_MEMORY_COST_KIB,
            minimum_time_cost=master_key.MIN_TIME_COST,
            maximum_time_cost=master_key.MAX_TIME_COST,
            minimum_parallelism=master_key.MIN_PARALLELISM,
            maximum_parallelism=master_key.MAX_PARALLELISM,
            salt_bytes=KDF_SALT_BYTES,
        )

    def passphrase_kdf_window_accepts(
        self,
        *,
        memory_cost: int,
        time_cost: int,
        parallelism: int,
        salt: bytes,
    ) -> bool:
        policy = self.passphrase_kdf_policy()
        return (
            policy.minimum_memory_cost_kib <= memory_cost <= policy.maximum_memory_cost_kib
            and policy.minimum_time_cost <= time_cost <= policy.maximum_time_cost
            and policy.minimum_parallelism <= parallelism <= policy.maximum_parallelism
            and len(salt) == policy.salt_bytes
        )

    def encrypt_record(
        self,
        plaintext: bytes,
        *,
        key: bytes,
        associated_data: bytes | None = None,
    ) -> ProfileRecordEncryptedBlob:
        try:
            blob = crypto.encrypt_record(plaintext, key=key, associated_data=associated_data)
            return ProfileRecordEncryptedBlob(nonce=blob.nonce, ciphertext=blob.ciphertext)
        except Exception as exc:
            raise ProfileRecordCryptoError("profile record encryption failed") from exc

    def decrypt_record(
        self,
        blob: ProfileRecordEncryptedBlob,
        *,
        key: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        try:
            adapter_blob = crypto.EncryptedBlob(nonce=blob.nonce, ciphertext=blob.ciphertext)
            return crypto.decrypt_record(adapter_blob, key=key, associated_data=associated_data)
        except Exception as exc:
            raise ProfileRecordCryptoError("profile record decryption failed") from exc

    def seal_with_passphrase(
        self,
        plaintext: bytes,
        *,
        passphrase: bytes,
        associated_data: bytes,
    ) -> ProfilePassphraseEncryptedRecord:
        try:
            parameters = master_key.KdfParams.default()
            sealing_key = master_key.derive_kek_with_params(
                passphrase,
                parameters.salt,
                memory_cost=parameters.memory_cost,
                time_cost=parameters.time_cost,
                parallelism=parameters.parallelism,
            )
            blob = crypto.encrypt_record(
                plaintext,
                key=sealing_key,
                associated_data=associated_data,
            )
        except Exception as exc:
            raise ProfileRecordCryptoError("profile passphrase record encryption failed") from exc
        return ProfilePassphraseEncryptedRecord(
            parameters=ProfilePassphraseKdfParameters(
                version=parameters.version,
                memory_cost=parameters.memory_cost,
                time_cost=parameters.time_cost,
                parallelism=parameters.parallelism,
                salt=parameters.salt,
            ),
            blob=ProfileRecordEncryptedBlob(nonce=blob.nonce, ciphertext=blob.ciphertext),
        )

    def open_with_passphrase(
        self,
        blob: ProfileRecordEncryptedBlob,
        *,
        passphrase: bytes,
        parameters: ProfilePassphraseKdfParameters,
        associated_data: bytes,
    ) -> bytes:
        policy = self.passphrase_kdf_policy()
        if parameters.version != policy.version or not self.passphrase_kdf_window_accepts(
            memory_cost=parameters.memory_cost,
            time_cost=parameters.time_cost,
            parallelism=parameters.parallelism,
            salt=parameters.salt,
        ):
            raise ProfileRecordCryptoError("profile passphrase KDF parameters are unsupported")
        try:
            sealing_key = master_key.derive_kek_with_params(
                passphrase,
                parameters.salt,
                memory_cost=parameters.memory_cost,
                time_cost=parameters.time_cost,
                parallelism=parameters.parallelism,
            )
            return crypto.decrypt_record(
                crypto.EncryptedBlob(nonce=blob.nonce, ciphertext=blob.ciphertext),
                key=sealing_key,
                associated_data=associated_data,
            )
        except Exception as exc:
            raise ProfileRecordCryptoError("profile passphrase record decryption failed") from exc


class _PersistenceProfileCustody:
    """Compose canonical persistence authorities behind the custody port."""

    def local_record_store(self) -> ProfileCustodyLocalRecordStore:
        return _PersistenceProfileCustodyLocalRecordStore()

    def archive_schema_version(self) -> int:
        return bucket.ARCHIVE_SCHEMA_VERSION

    def write_archive_container(
        self,
        target: Path,
        *,
        header: ProfileCapsuleArchiveHeaderMaterial,
        payload_bytes: bytes,
    ) -> None:
        bucket.write_sealed_archive(
            target,
            header=bucket.ExportArchiveHeader(
                product=header.product,
                bucket_id=header.bucket_id,
                manifest_digest=header.manifest_digest,
                archive_schema_version=header.archive_schema_version,
                created_at=header.created_at,
            ),
            payload_bytes=payload_bytes,
        )

    def read_archive_container(self, source: Path) -> ProfileCapsuleArchiveContentsMaterial:
        contents = bucket.read_sealed_archive(source)
        return ProfileCapsuleArchiveContentsMaterial(
            header=ProfileCapsuleArchiveHeaderMaterial(
                product=contents.header.product,
                bucket_id=contents.header.bucket_id,
                manifest_digest=contents.header.manifest_digest,
                archive_schema_version=contents.header.archive_schema_version,
                created_at=contents.header.created_at,
            ),
            payload_bytes=contents.payload_bytes,
        )

    def parse_capsule_members(
        self,
        *,
        envelope_bytes: bytes,
        sentinel_bytes: bytes,
        database_bytes: bytes,
    ) -> ProfileCustodyCapsuleSourceMaterial:
        return ProfileCustodyCapsuleSourceMaterial(
            password_envelope=custody.parse_profile_custody_envelope(envelope_bytes),
            sentinel=custody.parse_profile_custody_sentinel_record(sentinel_bytes),
            database_bytes=database_bytes,
        )

    def read_capsule_source(self, source: Path) -> ProfileCustodyCapsuleSourceMaterial:
        def required(relative: Path, maximum_bytes: int, subject: str) -> bytes:
            try:
                return custody.read_profile_custody_local_record(source / relative, maximum_bytes=maximum_bytes)
            except Exception as exc:
                raise ValueError(f"capsule source is missing or has an invalid {subject}") from exc

        envelope = custody.parse_profile_custody_envelope(
            required(
                _capsule_relative(StorageCategory.PROFILE_CAPSULE_PASSWORD_ENVELOPE),
                custody.PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
                "password envelope",
            )
        )
        sentinel = custody.parse_profile_custody_sentinel_record(
            required(
                _capsule_relative(StorageCategory.PROFILE_CAPSULE_DATA) / custody.PROFILE_CUSTODY_SENTINEL_FILENAME,
                custody.PROFILE_CUSTODY_SENTINEL_MAX_BYTES,
                "DEK sentinel",
            )
        )
        database_bytes = required(
            _capsule_relative(StorageCategory.BUCKET_DATABASE_FILE),
            custody.PROFILE_CUSTODY_DATA_FILE_MAX_BYTES,
            "profile database",
        )
        return ProfileCustodyCapsuleSourceMaterial(envelope, sentinel, database_bytes)

    def inventory_committed(
        self,
        profile_id: UUID,
        *,
        root: Path | None = None,
    ) -> ProfileCustodyInventoryPort:
        return custody.inventory_committed_profile_custody_capsule(profile_id, root=root)

    def create_capsule_label(self, *, profile_id: UUID, label: str) -> ProfileCustodyCapsuleLabelPort:
        return custody.ProfileCustodyCapsuleLabel.create(profile_id=profile_id, label=label)

    def staging_path(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> Path:
        return custody.profile_custody_staging_path(
            profile_id=profile_id,
            transaction_id=transaction_id,
            root=root,
        )

    def deletion_path(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> Path:
        return custody.profile_custody_deletion_path(
            profile_id=profile_id,
            transaction_id=transaction_id,
            root=root,
        )

    def committed_capsule_path(self, profile_id: UUID, *, root: Path) -> Path | None:
        return custody.recognize_current_profile_capsule(profile_id, root=root)

    def list_committed_profile_ids(self, *, root: Path) -> tuple[UUID, ...]:
        return custody.list_current_profile_custody_capsule_ids(root=root)

    def load_committed_capsule_label(self, profile_id: UUID, *, root: Path) -> ProfileCustodyCapsuleLabelPort:
        return custody.load_committed_profile_custody_label_record(profile_id, root=root)

    def verify_or_recover_initial_label_head(
        self,
        *,
        label: ProfileCustodyCapsuleLabelPort,
        source_witness: str,
        root: Path,
    ) -> ProfileCustodyLabelHeadPort:
        try:
            return custody.ProfileLabelHeadRepository(root=root).verify_or_recover_initial(
                label=_substrate_handle(label, custody.ProfileCustodyCapsuleLabel, "capsule label"),
                source_witness=source_witness,
            )
        except custody.ProfileCustodyRecordError as exc:
            raise ProfileCustodyRecordIntegrityError(str(exc)) from exc

    def load_staged_capsule_label(
        self,
        profile_id: UUID,
        transaction_id: UUID,
        *,
        root: Path,
    ) -> ProfileCustodyCapsuleLabelPort:
        return custody.load_staged_profile_custody_label_record(
            profile_id,
            transaction_id,
            root=root,
        )

    def stage_capsule(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        publication_kind: Literal["enroll", "restore"],
        password_envelope: ProfileCustodyEnvelopePort,
        sentinel: ProfileCustodySentinelPort,
        data_files: Mapping[str, bytes],
        label_record: ProfileCustodyCapsuleLabelPort,
        recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None,
        root: Path,
        published_at: datetime,
        stage_initializer: Callable[[Path], None] | None,
    ) -> Path:
        return custody.publish_profile_custody_capsule(
            profile_id=profile_id,
            transaction_id=transaction_id,
            publication_kind=publication_kind,
            password_envelope=_substrate_handle(
                password_envelope,
                custody.ProfileCustodyEnvelope,
                "password envelope",
            ),
            sentinel=_substrate_handle(sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel"),
            data_files={
                **data_files,
                custody.PROFILE_CUSTODY_LABEL_FILENAME: label_record.canonical_json_bytes(),
            },
            recovery_envelope=(
                None
                if recovery_envelope is None
                else _substrate_handle(
                    recovery_envelope,
                    custody.ProfileCustodyRecoveryEnvelope,
                    "recovery envelope",
                )
            ),
            root=root,
            published_at=published_at,
            stage_only=True,
            stage_initializer=stage_initializer,
        )

    def inventory_staged(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        root: Path,
    ) -> ProfileCustodyInventoryPort:
        return custody.inventory_staged_profile_custody_capsule(
            profile_id=profile_id,
            transaction_id=transaction_id,
            root=root,
        )

    def publish_staged(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> Path:
        return custody.publish_staged_profile_custody_capsule(
            profile_id=profile_id,
            transaction_id=transaction_id,
            root=root,
        )

    def write_deletion_marker(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        inventory_digest: str,
        root: Path,
    ) -> None:
        custody.write_profile_custody_deletion_marker(
            profile_id=profile_id,
            transaction_id=transaction_id,
            inventory_digest=inventory_digest,
            root=root,
        )

    def verify_deletion_marker(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        inventory_digest: str,
        root: Path,
    ) -> None:
        custody.verify_profile_custody_deletion_marker(
            profile_id=profile_id,
            transaction_id=transaction_id,
            inventory_digest=inventory_digest,
            root=root,
        )

    def verify_deletion_tombstone(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        inventory_digest: str,
        root: Path,
    ) -> None:
        custody.verify_profile_custody_deletion_tombstone(
            profile_id=profile_id,
            transaction_id=transaction_id,
            inventory_digest=inventory_digest,
            root=root,
        )

    def rename_capsule_for_deletion(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> Path:
        return custody.rename_profile_custody_capsule_for_deletion(
            profile_id=profile_id,
            transaction_id=transaction_id,
            root=root,
        )

    def remove_deletion_tombstone(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> None:
        custody.remove_profile_custody_deletion_tombstone(
            profile_id=profile_id,
            transaction_id=transaction_id,
            root=root,
        )

    def bucket_storage(self) -> ProfileBucketStoragePort:
        return _PersistenceProfileBucketStorage()

    def read_output_language_hint(self, *, storage_root: Path, bucket_id: str) -> str | None:
        return bucket.read_bucket_output_language_hint(
            storage_root=storage_root,
            bucket_id=bucket_id,
        )

    def secure_object_inventory(self) -> ProfileSecureObjectInventoryPort:
        return _PersistenceProfileSecureObjectInventory()

    def collect_profile_custody_carry(
        self,
        *,
        bucket_id: str,
        profile: StorageCustodyProfile,
    ) -> ProfileCustodyCarryMaterial:
        return _collect_profile_custody_carry(bucket_id=bucket_id, profile=profile)

    def restore_profile_custody_carry(
        self,
        carried_objects: tuple[CarriedSecureObject, ...],
        *,
        target_bucket_id: str,
    ) -> None:
        _restore_profile_custody_carry(carried_objects, target_bucket_id=target_bucket_id)

    def profile_snapshot_persistence(
        self,
        bucket_id: str,
        *,
        object_key: Callable[[str, str], str],
        objects: ProfileCustodySecureObjectRepositoryPort | None = None,
    ) -> ProfileSnapshotPersistencePort:
        resolved = (
            None if objects is None else _substrate_handle(objects, SecureObjectRepository, "secure-object repository")
        )
        return _PersistenceProfileSnapshotStore(
            bucket_id=bucket_id,
            object_key=object_key,
            objects=resolved,
        )

    def record_crypto(self) -> ProfileRecordCryptoPort:
        return _PersistenceProfileRecordCrypto()

    def create_registration_material(
        self,
        *,
        profile_id: UUID,
        password: str,
        dek: bytes,
        dek_epoch: str,
        salt: bytes,
        password_generation: int,
    ) -> ProfileCustodyRegistrationMaterial:
        calibration = custody.calibrate_profile_kdf(salt=salt)
        envelope = custody.create_profile_custody_password_envelope(
            profile_id=profile_id,
            password=password,
            dek=dek,
            dek_epoch=dek_epoch,
            kdf=calibration.parameters,
            password_generation=password_generation,
        )
        sentinel = custody.create_profile_custody_sentinel(envelope=envelope, dek=dek)
        return ProfileCustodyRegistrationMaterial(envelope=envelope, sentinel=sentinel)

    def create_recovery_enrollment_material(
        self,
        *,
        profile_id: UUID,
        dek: bytes,
        dek_epoch: str,
        salt: bytes,
    ) -> ProfileCustodyRecoveryEnrollmentMaterial:
        calibration = custody.calibrate_profile_kdf(salt=salt)
        recovery_key = generate_recovery_key()
        try:
            envelope = custody.create_profile_custody_recovery_envelope(
                profile_id=profile_id,
                recovery_secret=recovery_key.mnemonic,
                dek=dek,
                dek_epoch=dek_epoch,
                kdf=calibration.parameters,
            )
        except BaseException:
            recovery_key.wipe()
            raise
        return ProfileCustodyRecoveryEnrollmentMaterial(envelope=envelope, recovery_key=recovery_key)

    def export_recovery_artifact(
        self,
        recovery_envelope: ProfileCustodyRecoveryEnvelopePort,
        *,
        current_password: str,
        password_envelope: ProfileCustodyEnvelopePort,
        sentinel: ProfileCustodySentinelPort,
        target: Path,
    ) -> ProfileCustodyRecoveryArtifactExportReceiptPort:
        return _recovery_artifact_receipt(
            custody.export_profile_custody_recovery_artifact(
                _substrate_handle(recovery_envelope, custody.ProfileCustodyRecoveryEnvelope, "recovery envelope"),
                current_password=current_password,
                password_envelope=_substrate_handle(
                    password_envelope, custody.ProfileCustodyEnvelope, "password envelope"
                ),
                sentinel=_substrate_handle(sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel"),
                target=target,
            )
        )

    def prove_recovery_artifact(
        self,
        source: Path,
        *,
        recovery_secret: str,
        expected_profile_id: UUID,
        expected_dek_epoch: str,
        sentinel: ProfileCustodySentinelPort,
    ) -> ProfileCustodyRecoveryUnlockPort:
        substrate_sentinel = _substrate_handle(sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel")
        artifact = custody.import_profile_custody_recovery_artifact(
            source,
            expected_profile_id=expected_profile_id,
            expected_dek_epoch=expected_dek_epoch,
        )
        return custody.unlock_imported_profile_custody_recovery_artifact(
            artifact,
            recovery_secret,
            sentinel=substrate_sentinel,
            expected_profile_id=expected_profile_id,
            expected_dek_epoch=expected_dek_epoch,
        )

    def verify_dek_against_sentinel(
        self,
        *,
        dek: bytes,
        profile_id: UUID,
        dek_epoch: str,
        sentinel: ProfileCustodySentinelPort,
    ) -> None:
        custody.verify_profile_custody_sentinel(
            dek=dek,
            profile_id=profile_id,
            dek_epoch=dek_epoch,
            sentinel=_substrate_handle(sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel"),
        )

    def recovery_envelope_path(self, capsule_path: Path) -> Path:
        return capsule_path / "custody" / custody.PROFILE_CUSTODY_RECOVERY_FILENAME

    def unlock_password(
        self,
        material: ProfileCustodyPasswordProofMaterialPort,
        *,
        password: str,
    ) -> ProfileCustodyUnlockPort:
        return custody.unlock_profile_custody(
            _substrate_handle(material.envelope, custody.ProfileCustodyEnvelope, "password envelope"),
            password,
            sentinel=_substrate_handle(material.sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel"),
        )

    def replace_password_envelope(
        self,
        *,
        profile_id: UUID,
        current: ProfileCustodyEnvelopePort,
        rotated: ProfileCustodyEnvelopePort,
        root: Path,
    ) -> None:
        custody.replace_committed_profile_custody_envelope(
            profile_id,
            rotated.canonical_json_bytes(),
            expected_sha256=prefixed_digest(current.canonical_json_bytes()),
            root=root,
        )

    def load_password_material(
        self,
        profile_id: UUID,
        *,
        root: Path | None = None,
    ) -> ProfileCustodyPasswordMaterialPort:
        return custody.load_committed_profile_password_material(profile_id, root=root)

    def is_authentication_proof_failure(
        self,
        error: BaseException,
        *,
        operation: ProfilePasswordProofOperation,
    ) -> bool:
        expected = (
            custody.ProfileCustodyRecoverySecretError
            if operation is ProfilePasswordProofOperation.RECOVERY_RESTORE
            else custody.ProfileCustodyPasswordError
        )
        return isinstance(error, expected)

    def refuse_login_without_password_channel(self) -> NoReturn:
        raise custody.ProfileCustodyPasswordError("profile login requires an explicit password channel")

    def is_authentication_failure(self, error: BaseException) -> bool:
        return isinstance(error, (KeyringUnavailableError, MasterKeyMaterialMissingError))

    def is_keyring_unavailable(self, error: BaseException) -> bool:
        return isinstance(error, KeyringUnavailableError)

    def is_persistence_failure(self, error: BaseException) -> bool:
        return isinstance(error, PersistenceError)

    def secure_object_namespace(self) -> ProfileCustodySecureObjectNamespace:
        return ProfileCustodySecureObjectNamespace(
            namespace=USER_PROFILE_VALUE_NAMESPACE.namespace,
            sensitivity=USER_PROFILE_VALUE_NAMESPACE.sensitivity,
            schema_version=USER_PROFILE_VALUE_NAMESPACE.schema_version,
        )

    @contextmanager
    def secure_object_repository(
        self,
        *,
        profile_id: UUID,
        dek: bytes,
        root: Path,
        database_file: Path | None = None,
    ) -> Generator[ProfileCustodySecureObjectRepositoryPort]:
        active = master_key.current_active_bucket_session()
        if database_file is None and master_key.session_serves_bucket(active, str(profile_id)):
            settings = Settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(profile_id))
            yield secure_object_repository_for_bucket(str(profile_id), settings)
            return

        if database_file is None:
            database_file = bucket.bucket_paths(root, str(profile_id)).database_file
        with (
            self._temporary_session(profile_id=profile_id, dek=dek, root=root),
            secure_object_repository_for_staged_bucket(str(profile_id), database_file=database_file) as staged,
        ):
            yield staged

    @contextmanager
    def _temporary_session(self, *, profile_id: UUID, dek: bytes, root: Path) -> Generator[None]:
        instant = _utc_now()
        bridge = master_key.BucketSession.open_resumed(
            bucket_id=str(profile_id),
            dek=dek,
            idle_minutes=1,
            opened_at=instant,
            idle_deadline=instant + timedelta(minutes=1),
            absolute_deadline=instant + timedelta(minutes=1),
            storage_root=root,
        )
        try:
            with master_key.activate_session(bridge):
                yield
        finally:
            bridge.close()

    def bucket_event_history_repository(
        self,
        *,
        objects: ProfileCustodySecureObjectRepositoryPort | None = None,
    ) -> ProfileCustodyBucketEventHistoryPort:
        resolved = (
            None if objects is None else _substrate_handle(objects, SecureObjectRepository, "secure-object repository")
        )
        return BucketEventHistoryRepository(objects=resolved)


def build_profile_custody_port() -> ProfileCustodyPort:
    """Build a stateless adapter over the canonical custody authorities."""
    return _PersistenceProfileCustody()


__all__ = ["build_profile_custody_port"]
