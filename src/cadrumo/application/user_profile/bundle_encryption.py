"""Passphrase encryption for portable profile-bundle exports."""

from __future__ import annotations

import base64
import binascii
from typing import Final

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.external_constants import UTF_8_ENCODING
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.user_profile.portable_export import UserProfilePortableExport
from .custody_ports import (
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


__all__ = [
    "EncryptedProfileBundleExport",
    "encrypt_profile_bundle_for_passphrase",
]
