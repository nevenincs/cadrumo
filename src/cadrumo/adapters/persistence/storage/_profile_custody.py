"""Concrete persistence adapter for the application profile-custody port."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from ....application.user_profile import (
    ProfileBucketStoragePathsPort,
    ProfileBucketStoragePort,
    ProfileCapsuleArchiveContentsMaterial,
    ProfileCapsuleArchiveHeaderMaterial,
    ProfileCustodyBucketEventHistoryPort,
    ProfileCustodyCapsuleSourceMaterial,
    ProfileCustodyEnvelopePort,
    ProfileCustodyInventoryPort,
    ProfileCustodyLocalRecordStore,
    ProfileCustodyPasswordMaterialPort,
    ProfileCustodyPasswordProofMaterialPort,
    ProfileCustodyPort,
    ProfileCustodyRecoveryArtifactExportReceiptPort,
    ProfileCustodyRecoveryEnrollmentMaterial,
    ProfileCustodyRecoveryEnvelopePort,
    ProfileCustodyRecoveryUnlockPort,
    ProfileCustodyRegistrationMaterial,
    ProfileCustodySecureObjectNamespace,
    ProfileCustodySecureObjectRepositoryPort,
    ProfileCustodySentinelPort,
    ProfileCustodyUnlockPort,
    ProfilePasswordProofOperation,
    ProfileRecordCryptoError,
    ProfileRecordCryptoPort,
    ProfileRecordEncryptedBlob,
    ProfileSecureObjectInventoryPort,
)
from ....core.config import Settings
from ....core.hashing import prefixed_digest
from ....core.time import now as _utc_now
from ..profile.buckets import BucketEventHistoryRepository
from . import (
    USER_PROFILE_VALUE_NAMESPACE,
    KeyringUnavailableError,
    MasterKeyMaterialMissingError,
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


class _PersistenceProfileRecordCrypto:
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
                Path("custody/envelope.v1.json"),
                custody.PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
                "password envelope",
            )
        )
        sentinel = custody.parse_profile_custody_sentinel_record(
            required(
                Path("data/dek.sentinel.v1.json"),
                custody.PROFILE_CUSTODY_SENTINEL_MAX_BYTES,
                "DEK sentinel",
            )
        )
        database_bytes = required(
            Path("db/cadrumo.db"), custody.PROFILE_CUSTODY_DATA_FILE_MAX_BYTES, "profile database"
        )
        return ProfileCustodyCapsuleSourceMaterial(envelope, sentinel, database_bytes)

    def inventory_committed(
        self,
        profile_id: UUID,
        *,
        root: Path | None = None,
    ) -> ProfileCustodyInventoryPort:
        return custody.inventory_committed_profile_custody_capsule(profile_id, root=root)

    def bucket_storage(self) -> ProfileBucketStoragePort:
        return _PersistenceProfileBucketStorage()

    def secure_object_inventory(self) -> ProfileSecureObjectInventoryPort:
        return _PersistenceProfileSecureObjectInventory()

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
