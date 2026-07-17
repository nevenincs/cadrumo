"""Passphrase encryption for portable profile-bundle exports."""

from __future__ import annotations

import base64

from pydantic import BaseModel, Field

from ...adapters.persistence.storage.crypto import EncryptedBlob, decrypt_record, encrypt_record
from ...adapters.persistence.storage.master_key import KdfParams, derive_kek_with_params
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import UTF_8_ENCODING
from ...domain.user_profile import UserProfilePortableExport, UserProfileValidationError
from ._bundle import (
    BUNDLE_SCHEMA_VERSION,
    UnsupportedBundleSchemaVersionError,
    validate_bundle_payload,
)

_ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION = 1
_ENCRYPTED_BUNDLE_AAD = b"cadrumo.user-profile.portable-export.v1"


class EncryptedProfileBundleExport(BaseModel):
    """Encrypted transport envelope for a serialized profile-bundle payload.

    The ciphertext wraps the exact ``UserProfilePortableExport`` JSON bytes.
    The envelope schema is transport metadata only; after decryption, callers
    still validate the original bundle model and its ``bundle_schema_version``.
    """

    model_config = _STRICT_FROZEN

    encrypted_bundle_schema_version: int = Field(default=_ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION, ge=1)
    payload_model: str = "UserProfilePortableExport"
    payload_schema_version: int
    kdf: str = "argon2id"
    kdf_version: int
    memory_cost: int
    time_cost: int
    parallelism: int
    salt_b64: str
    ciphertext_b64: str


# Encrypted envelopes are user-profile input, so preserve the registered
# validation error rather than introducing a second unregistered error class.
EncryptedProfileBundleError = UserProfileValidationError


def encrypt_profile_bundle_for_passphrase(
    bundle: UserProfilePortableExport,
    *,
    passphrase: str,
) -> EncryptedProfileBundleExport:
    """Encrypt ``bundle`` under ``passphrase`` and return a transport envelope."""
    params = KdfParams.default()
    sealing_key = derive_kek_with_params(
        passphrase.encode(UTF_8_ENCODING),
        params.salt,
        memory_cost=params.memory_cost,
        time_cost=params.time_cost,
        parallelism=params.parallelism,
    )
    payload = bundle.model_dump_json().encode(UTF_8_ENCODING)
    encrypted = encrypt_record(payload, key=sealing_key, associated_data=_ENCRYPTED_BUNDLE_AAD)
    return EncryptedProfileBundleExport(
        payload_schema_version=bundle.bundle_schema_version,
        kdf_version=params.version,
        memory_cost=params.memory_cost,
        time_cost=params.time_cost,
        parallelism=params.parallelism,
        salt_b64=base64.b64encode(params.salt).decode("ascii"),
        ciphertext_b64=base64.b64encode(encrypted.to_wire()).decode("ascii"),
    )


def decrypt_profile_bundle_with_passphrase(
    envelope: EncryptedProfileBundleExport,
    *,
    passphrase: str,
) -> UserProfilePortableExport:
    """Decrypt ``envelope`` and validate the wrapped ``UserProfilePortableExport``.

    Payload validation routes through
    :func:`~cadrumo.application.user_profile.validate_bundle_payload`, so an
    non-current ``bundle_schema_version`` propagates as
    :class:`UnsupportedBundleSchemaVersionError` (naming the version) rather
    than being flattened into the generic envelope error.
    """
    if envelope.encrypted_bundle_schema_version > _ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION:
        raise EncryptedProfileBundleError(
            "encrypted profile-bundle envelope schema was written by a newer application",
        )
    if envelope.payload_model != "UserProfilePortableExport":
        raise EncryptedProfileBundleError(
            "encrypted profile-bundle envelope declares the wrong payload model",
        )
    if envelope.payload_schema_version != BUNDLE_SCHEMA_VERSION:
        raise EncryptedProfileBundleError(
            "encrypted profile-bundle envelope declares an unsupported payload schema",
        )
    if envelope.kdf != "argon2id":
        raise EncryptedProfileBundleError(
            "encrypted profile-bundle envelope declares an unsupported KDF",
        )
    try:
        salt = base64.b64decode(envelope.salt_b64.encode("ascii"), validate=True)
        ciphertext = base64.b64decode(envelope.ciphertext_b64.encode("ascii"), validate=True)
        sealing_key = derive_kek_with_params(
            passphrase.encode(UTF_8_ENCODING),
            salt,
            memory_cost=envelope.memory_cost,
            time_cost=envelope.time_cost,
            parallelism=envelope.parallelism,
        )
        plaintext = decrypt_record(
            EncryptedBlob.from_wire(ciphertext),
            key=sealing_key,
            associated_data=_ENCRYPTED_BUNDLE_AAD,
        )
    except Exception as exc:
        raise EncryptedProfileBundleError(
            "encrypted profile-bundle payload could not be decrypted",
        ) from exc
    try:
        return validate_bundle_payload(
            plaintext,
            expected_written_version=envelope.payload_schema_version,
        )
    except UnsupportedBundleSchemaVersionError:
        raise
    except Exception as exc:
        raise EncryptedProfileBundleError(
            "encrypted profile-bundle payload could not be validated",
        ) from exc


__all__ = [
    "EncryptedProfileBundleError",
    "EncryptedProfileBundleExport",
    "decrypt_profile_bundle_with_passphrase",
    "encrypt_profile_bundle_for_passphrase",
]
