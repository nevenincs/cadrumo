"""Passphrase encryption for portable profile-bundle exports."""

from __future__ import annotations

import base64
import binascii
from typing import Final

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.external_constants import UTF_8_ENCODING
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.user_profile.errors import UserProfileValidationError
from ...domain.user_profile.portable_export import UserProfilePortableExport
from .bundle import (
    SUPPORTED_BUNDLE_SCHEMA_VERSIONS,
    UnsupportedBundleSchemaVersionError,
    validate_bundle_payload,
)
from .custody_ports import (
    ProfilePassphraseKdfParameters,
    ProfileRecordEncryptedBlob,
    default_profile_record_crypto_port,
)

_ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION: Final[int] = 1
_ENCRYPTED_BUNDLE_PAYLOAD_MODEL: Final[str] = "UserProfilePortableExport"
_ENCRYPTED_BUNDLE_KDF: Final[str] = "argon2id"
_ENCRYPTED_BUNDLE_AAD = b"cadrumo.user-profile.portable-export.v1"


class EncryptedProfileBundleExport(BaseModel):
    """Encrypted transport envelope for a serialized profile-bundle payload.

    The ciphertext wraps the exact ``UserProfilePortableExport`` JSON bytes.
    The envelope schema is transport metadata only; after decryption, callers
    still validate the original bundle model and its ``bundle_schema_version``.

    Every marker that routes how the ciphertext is interpreted --
    ``encrypted_bundle_schema_version``, ``payload_model``, ``kdf`` and
    ``kdf_version`` -- is required and compared for equality on the read path.
    The first three carry no default, and a default equal to the accepted value makes that comparison
    blind to the one payload it exists to catch: a stored envelope omitting
    the key hydrates AS the accepted value and passes a check the writer never
    actually made. Every field on this record is stamped explicitly by
    :func:`encrypt_profile_bundle_for_passphrase`.

    The three Argon2 cost axes and the salt length carry the same window as the
    composed persistence KDF policy that the writer stamps them from. They were
    bare integers and a bare string, which made this the one storage KDF record that could describe an
    arbitrarily weak derivation: eight kibibytes, one iteration, a one-byte
    salt. The writer never emitted such a set, so nothing this build wrote was
    weak -- what the looseness cost was that a re-exported envelope could
    circulate as an application-grade encrypted bundle while being
    brute-forceable, and that a structurally invalid salt was indistinguishable
    at the boundary from a wrong passphrase, sending an operator to recover a
    passphrase that was never wrong.

    Reading the window through the application crypto port rather than
    restating it is what keeps the bound this record validates against from
    drifting away from the parameters the writer stamps.
    """

    model_config = _STRICT_FROZEN

    encrypted_bundle_schema_version: int = Field(ge=1)
    payload_model: str = Field(min_length=1)
    payload_schema_version: int
    kdf: str = Field(min_length=1)
    kdf_version: int
    memory_cost: int
    time_cost: int
    parallelism: int
    salt_b64: str
    ciphertext_b64: str

    @field_validator("salt_b64")
    @classmethod
    def _check_salt_b64(cls, value: str) -> str:
        """Refuse a salt that is not canonical base64."""
        try:
            base64.b64decode(value.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error) as exc:
            raise ValueError("salt_b64 must be canonical base64") from exc
        return value

    @model_validator(mode="after")
    def _check_kdf_window(self) -> EncryptedProfileBundleExport:
        """Refuse KDF costs and salt lengths outside the composed policy."""
        salt = base64.b64decode(self.salt_b64.encode("ascii"), validate=True)
        crypto = default_profile_record_crypto_port()
        policy = crypto.passphrase_kdf_policy()
        if len(salt) != policy.salt_bytes:
            raise ValueError(f"salt_b64 must encode exactly {policy.salt_bytes} bytes")
        if not crypto.passphrase_kdf_window_accepts(
            memory_cost=self.memory_cost,
            time_cost=self.time_cost,
            parallelism=self.parallelism,
            salt=salt,
        ):
            raise ValueError("passphrase KDF parameters are outside the supported window")
        return self


def encrypt_profile_bundle_for_passphrase(
    bundle: UserProfilePortableExport,
    *,
    passphrase: str,
) -> EncryptedProfileBundleExport:
    """Encrypt ``bundle`` under ``passphrase`` and return a transport envelope."""
    payload = bundle.model_dump_json().encode(UTF_8_ENCODING)
    encrypted = default_profile_record_crypto_port().seal_with_passphrase(
        payload,
        passphrase=passphrase.encode(UTF_8_ENCODING),
        associated_data=_ENCRYPTED_BUNDLE_AAD,
    )
    params = encrypted.parameters
    return EncryptedProfileBundleExport(
        encrypted_bundle_schema_version=_ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION,
        payload_model=_ENCRYPTED_BUNDLE_PAYLOAD_MODEL,
        payload_schema_version=bundle.bundle_schema_version,
        kdf=_ENCRYPTED_BUNDLE_KDF,
        kdf_version=params.version,
        memory_cost=params.memory_cost,
        time_cost=params.time_cost,
        parallelism=params.parallelism,
        salt_b64=base64.b64encode(params.salt).decode("ascii"),
        ciphertext_b64=base64.b64encode(encrypted.blob.to_wire()).decode("ascii"),
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

    The two version gates below are deliberately different shapes, and the
    difference is the presence of a migration mechanism. The PAYLOAD version is
    checked against a floor-to-current range carrying a per-hop upgrader chain,
    so an older payload has a defined route forward and the range is designed to
    widen once the floor freezes; it is single-valued today only because the
    floor still equals the current version. The TRANSPORT envelope has no floor,
    no upgrader chain and no lineage enrolment, so nothing could ever carry an
    older layout forward -- accepting one would mean reading bytes under a
    structure this build does not implement. A ceiling there refused a newer
    envelope while admitting every older one, which is the direction with no
    recovery behind it, so the transport gate is exact.
    """
    if envelope.encrypted_bundle_schema_version != _ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION:
        raise UserProfileValidationError(
            translated_message="errors.refused.refused_user_profile_validation",
            context={
                "envelope_schema_version": str(envelope.encrypted_bundle_schema_version),
                "supported_schema_version": str(_ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION),
            },
        )
    if envelope.payload_model != _ENCRYPTED_BUNDLE_PAYLOAD_MODEL:
        raise UserProfileValidationError(
            translated_message="errors.refused.refused_user_profile_validation",
            context={"payload_model_expected": False},
        )
    if envelope.payload_schema_version not in SUPPORTED_BUNDLE_SCHEMA_VERSIONS:
        raise UserProfileValidationError(
            translated_message="errors.refused.refused_user_profile_validation",
            context={"payload_schema_supported": False},
        )
    if envelope.kdf != _ENCRYPTED_BUNDLE_KDF:
        raise UserProfileValidationError(
            translated_message="errors.refused.refused_user_profile_validation",
            context={"kdf_supported": False},
        )
    # Gated against the Argon2 ALGORITHM version the writer stamps --
    # deliberately not against the
    # file-backed provider's ``KDF_PARAMS_VERSION``, a different concept naming
    # the master.kdf record SHAPE. The two are unequal, so confusing them would
    # refuse every bundle this build writes.
    #
    crypto = default_profile_record_crypto_port()
    kdf_policy = crypto.passphrase_kdf_policy()
    if envelope.kdf_version != kdf_policy.version:
        raise UserProfileValidationError(
            translated_message="errors.refused.refused_user_profile_validation",
            context={
                "envelope_kdf_version": str(envelope.kdf_version),
                "supported_kdf_version": str(kdf_policy.version),
            },
        )
    try:
        salt = base64.b64decode(envelope.salt_b64.encode("ascii"), validate=True)
        ciphertext = base64.b64decode(envelope.ciphertext_b64.encode("ascii"), validate=True)
        plaintext = crypto.open_with_passphrase(
            ProfileRecordEncryptedBlob.from_wire(ciphertext),
            passphrase=passphrase.encode(UTF_8_ENCODING),
            parameters=ProfilePassphraseKdfParameters(
                version=envelope.kdf_version,
                memory_cost=envelope.memory_cost,
                time_cost=envelope.time_cost,
                parallelism=envelope.parallelism,
                salt=salt,
            ),
            associated_data=_ENCRYPTED_BUNDLE_AAD,
        )
    except Exception as exc:
        raise UserProfileValidationError(
            translated_message="errors.refused.refused_user_profile_validation",
            context={"payload_decrypted": False},
        ) from exc
    try:
        return validate_bundle_payload(
            plaintext,
            expected_written_version=envelope.payload_schema_version,
        )
    except UnsupportedBundleSchemaVersionError:
        raise
    except Exception as exc:
        raise UserProfileValidationError(
            translated_message="errors.refused.refused_user_profile_validation",
            context={"payload_valid": False},
        ) from exc


__all__ = [
    "EncryptedProfileBundleExport",
    "decrypt_profile_bundle_with_passphrase",
    "encrypt_profile_bundle_for_passphrase",
]
