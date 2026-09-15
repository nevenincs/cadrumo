"""Persistence and cryptographic adapter for recipient-encrypted packages.

This module is the outward implementation of the application-owned
recipient-encryption capability.  It owns the X25519, HKDF, and AEAD details
and translates their wire values and failures at the application boundary.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from pydantic import ValidationError

from ....application.modelo.recipient_encryption import (
    RecipientDecryptedPackage,
    RecipientEncryptedPackage,
    RecipientEncryptionCapability,
    RecipientEncryptionKeypair,
)
from ....application.modelo.review_package_recipient_encryption import (
    RecipientDecryptionError,
    RecipientEncryptionError,
    RecipientPackageExpiredError,
)
from ....core.external_constants import UTF_8_ENCODING
from ....core.identity.bucket import canonical_bucket_id
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....core.time.clock import now as _utc_now
from ..storage.crypto.aead import EncryptedBlob, decrypt_record, derive_key, encrypt_record
from ..storage.errors import (
    DecryptionError,
    EncryptionError,
    KeyDerivationError,
    SecureObjectRevisionConflictError,
    StorageError,
)
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE as _NAMESPACE,
)
from ..storage.sql.secure_objects import SecureObjectRepository

_HKDF_CONTEXT_PREFIX = b"cadrumo.review_package.recipient_encryption.v1"
_REPLAY_NONCE_BYTES = 32


def _hkdf_context(recipient_public_key_hex: str) -> bytes:
    """Return the domain-separated HKDF context for one recipient key."""
    return _HKDF_CONTEXT_PREFIX + b":" + recipient_public_key_hex.encode("ascii")


def _associated_data(recipient_public_key_hex: str) -> bytes:
    """Return the AEAD associated data binding ciphertext to one recipient."""
    return b"cadrumo.review_package.recipient:" + recipient_public_key_hex.encode("ascii")


def _recipient_encryption_key_object_key(bucket_id: str) -> str:
    """Return the namespace-owned natural key for one bucket's keypair."""
    return f"review-package-recipient-encryption-key:{canonical_bucket_id(bucket_id)}"


class RecipientEncryptionAdapter:
    """Concrete recipient-encryption capability backed by secure objects."""

    def __init__(self, *, repository: SecureObjectRepository | None = None, bucket_id: str | None = None) -> None:
        """Bind optional keypair persistence while retaining stateless cryptographic operations."""
        self._repository = repository
        self._bucket_id = canonical_bucket_id(bucket_id) if bucket_id is not None else None

    def _keypair_repository(self) -> SecureObjectRepository:
        if self._repository is None:
            raise RecipientEncryptionError(
                "recipient encryption keypair persistence requires a secure-object repository",
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            )
        return self._repository

    def _bound_bucket_id(self, bucket_id: str) -> str:
        normalized = canonical_bucket_id(bucket_id)
        if self._bucket_id is not None and normalized != self._bucket_id:
            raise RecipientEncryptionError(
                "recipient encryption capability is bound to a different bucket",
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            )
        return normalized

    def _load_keypair(self, *, bucket_id: str, object_key: str) -> RecipientEncryptionKeypair | None:
        repository = self._keypair_repository()
        try:
            record = repository.load(
                _NAMESPACE.namespace,
                object_key,
                expected_class=_NAMESPACE.sensitivity,
                max_supported_version=_NAMESPACE.schema_version,
            )
        except (OSError, StorageError) as exc:
            raise RecipientEncryptionError(
                "unable to load recipient encryption keypair",
                context={"namespace": _NAMESPACE.namespace, "object_key": object_key},
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            ) from exc
        if record is None:
            return None
        try:
            keypair = RecipientEncryptionKeypair.model_validate_json(record.payload)
        except (TypeError, ValueError, ValidationError) as exc:
            raise RecipientEncryptionError(
                "stored recipient encryption keypair is not well formed",
                context={"namespace": _NAMESPACE.namespace, "object_key": object_key},
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            ) from exc
        if str(keypair.bucket_id) != bucket_id:
            raise RecipientEncryptionError(
                "stored recipient encryption keypair does not belong to the bucket it was read from",
                context={"namespace": _NAMESPACE.namespace, "object_key": object_key},
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            )
        return keypair

    def ensure_keypair(
        self,
        *,
        bucket_id: str,
        generated_at: datetime | None = None,
    ) -> RecipientEncryptionKeypair:
        """Load or atomically mint one bucket-scoped X25519 keypair."""
        normalized_bucket_id = self._bound_bucket_id(bucket_id)
        object_key = _recipient_encryption_key_object_key(normalized_bucket_id)
        existing = self._load_keypair(bucket_id=normalized_bucket_id, object_key=object_key)
        if existing is not None:
            return existing

        private_key = X25519PrivateKey.generate()
        keypair = RecipientEncryptionKeypair(
            bucket_id=normalized_bucket_id,
            private_key_hex=private_key.private_bytes_raw().hex(),
            public_key_hex=private_key.public_key().public_bytes_raw().hex(),
            created_at=generated_at or _utc_now(),
        )
        try:
            self._keypair_repository().save(
                namespace=_NAMESPACE.namespace,
                object_key=object_key,
                classification=_NAMESPACE.sensitivity,
                schema_version=_NAMESPACE.schema_version,
                written_at=keypair.created_at,
                payload=keypair.model_dump_json().encode(UTF_8_ENCODING),
                write_provenance="adapters.persistence.profile.review_package_recipient_encryption",
                expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
            )
        except SecureObjectRevisionConflictError as exc:
            winner = self._load_keypair(bucket_id=normalized_bucket_id, object_key=object_key)
            if winner is None:
                raise RecipientEncryptionError(
                    "recipient encryption keypair creation conflicted but no winner was readable",
                    context={"namespace": _NAMESPACE.namespace, "object_key": object_key},
                    translated_message="application.modelo.errors.recipient_registry_load_failed",
                ) from exc
            return winner
        except (OSError, StorageError) as exc:
            raise RecipientEncryptionError(
                "unable to persist recipient encryption keypair",
                context={"namespace": _NAMESPACE.namespace, "object_key": object_key},
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            ) from exc
        return keypair

    def encrypt(
        self,
        package_bytes: bytes,
        *,
        recipient_public_key_hex: str,
        review_only: bool = False,
        valid_for: timedelta | None = None,
        issued_at: datetime | None = None,
    ) -> RecipientEncryptedPackage:
        """Seal bytes for a recipient using X25519 ECIES over project AEAD."""
        try:
            recipient_public_key = X25519PublicKey.from_public_bytes(bytes.fromhex(recipient_public_key_hex))
        except (TypeError, ValueError, UnicodeError) as exc:
            raise RecipientEncryptionError(
                "recipient_public_key_hex is not a well-formed X25519 public key",
                translated_message="application.modelo.errors.recipient_encryption_invalid_key",
            ) from exc

        if valid_for is not None and valid_for <= timedelta(0):
            raise RecipientEncryptionError(
                "valid_for must be a strictly positive duration",
                translated_message="application.modelo.errors.recipient_encryption_invalid_key",
            )

        try:
            ephemeral_private_key = X25519PrivateKey.generate()
            ephemeral_public_key = ephemeral_private_key.public_key()
            ephemeral_public_key_bytes = ephemeral_public_key.public_bytes_raw()
            shared_secret = ephemeral_private_key.exchange(recipient_public_key)
            derived_key = derive_key(
                key_material=shared_secret,
                salt=ephemeral_public_key_bytes,
                context=_hkdf_context(recipient_public_key_hex),
            )
            encrypted = encrypt_record(
                package_bytes,
                key=derived_key,
                associated_data=_associated_data(recipient_public_key_hex),
            )
        except (EncryptionError, KeyDerivationError, TypeError, ValueError, UnicodeError) as exc:
            raise RecipientEncryptionError(
                "recipient-encrypted package could not be sealed",
                translated_message="application.modelo.errors.recipient_encryption_invalid_key",
            ) from exc

        envelope_issued_at = issued_at or _utc_now()
        envelope_valid_until = envelope_issued_at + valid_for if valid_for is not None else None
        return RecipientEncryptedPackage(
            ephemeral_public_key_hex=ephemeral_public_key_bytes.hex(),
            recipient_public_key_hex=recipient_public_key_hex,
            ciphertext=encrypted.to_wire(),
            envelope_nonce_hex=secrets.token_hex(_REPLAY_NONCE_BYTES),
            issued_at=envelope_issued_at,
            valid_until=envelope_valid_until,
            review_only=review_only,
        )

    def decrypt(
        self,
        envelope: RecipientEncryptedPackage,
        *,
        recipient_private_key_hex: str,
        now: datetime | None = None,
    ) -> RecipientDecryptedPackage:
        """Open one recipient envelope and return its application DTO."""
        evaluated_at = now or _utc_now()
        if envelope.valid_until is not None and evaluated_at >= envelope.valid_until:
            raise RecipientPackageExpiredError(
                "recipient-encrypted package has expired; the recipient must request a fresh package",
                translated_message="application.modelo.errors.recipient_decryption_failed",
            )

        try:
            recipient_private_key = X25519PrivateKey.from_private_bytes(bytes.fromhex(recipient_private_key_hex))
            recipient_public_key_hex = recipient_private_key.public_key().public_bytes_raw().hex()
        except (TypeError, ValueError, UnicodeError) as exc:
            raise RecipientDecryptionError(
                "recipient_private_key_hex is not a well-formed X25519 private key",
                translated_message="application.modelo.errors.recipient_decryption_failed",
            ) from exc

        if recipient_public_key_hex != envelope.recipient_public_key_hex:
            raise RecipientDecryptionError(
                "recipient_private_key does not match the envelope's declared recipient public key",
                translated_message="application.modelo.errors.recipient_decryption_failed",
            )

        try:
            ephemeral_public_key = X25519PublicKey.from_public_bytes(bytes.fromhex(envelope.ephemeral_public_key_hex))
            shared_secret = recipient_private_key.exchange(ephemeral_public_key)
            derived_key = derive_key(
                key_material=shared_secret,
                salt=bytes.fromhex(envelope.ephemeral_public_key_hex),
                context=_hkdf_context(envelope.recipient_public_key_hex),
            )
            recovered = decrypt_record(
                EncryptedBlob.from_wire(envelope.ciphertext),
                key=derived_key,
                associated_data=_associated_data(envelope.recipient_public_key_hex),
            )
        except (DecryptionError, EncryptionError, KeyDerivationError, TypeError, ValueError, UnicodeError) as exc:
            raise RecipientDecryptionError(
                "recipient-encrypted package failed AEAD authentication",
                translated_message="application.modelo.errors.recipient_decryption_failed",
            ) from exc

        try:
            return RecipientDecryptedPackage(package_bytes=recovered, review_only=envelope.review_only)
        except ValidationError as exc:
            raise RecipientDecryptionError(
                "recipient-encrypted package contained an invalid plaintext payload",
                translated_message="application.modelo.errors.recipient_decryption_failed",
            ) from exc


def build_recipient_encryption_capability(*, bucket_id: str) -> RecipientEncryptionCapability:
    """Bind the concrete capability to the secure repository for ``bucket_id``."""
    normalized_bucket_id = canonical_bucket_id(bucket_id)
    return RecipientEncryptionAdapter(
        repository=secure_object_repository_for_bucket(normalized_bucket_id),
        bucket_id=normalized_bucket_id,
    )


__all__ = [
    "RecipientEncryptionAdapter",
    "build_recipient_encryption_capability",
]
