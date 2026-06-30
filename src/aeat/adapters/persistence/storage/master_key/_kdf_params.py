"""Canonical Argon2id parameter record.

Strict pydantic v2 model declaring the Argon2id KEK-derivation parameters
the substrate accepts. The :meth:`KdfParams.default` classmethod
materialises the OWASP 2024 Password Storage Cheat Sheet baseline:

- ``algorithm`` = ``"argon2id"``
- ``version`` = ``19`` (Argon2 v1.3)
- ``memory_cost`` = ``19 * 1024`` KiB (19 MiB)
- ``time_cost`` = ``2`` iterations
- ``parallelism`` = ``1`` lane
- ``salt`` = 16 bytes
- ``output_length`` = 32 bytes

Validators reject parameter sets outside the supported window so a
tampered manifest cannot drive the KDF into a weaker regime at unlock.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator

from .._kdf_salt import KDF_SALT_BYTES, decode_kdf_salt, encode_kdf_salt, require_kdf_salt_length
from ..errors import StorageValidationError

if TYPE_CHECKING:
    from ..bucket import ManifestKdfParams

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

_SALT_BYTES = KDF_SALT_BYTES
_OUTPUT_BYTES = 32
_ARGON2_V13 = 19
_MIN_MEMORY_COST_KIB = 19 * 1024
_MAX_MEMORY_COST_KIB = 1024 * 1024
_MIN_TIME_COST = 2
_MAX_TIME_COST = 16
_MIN_PARALLELISM = 1
_MAX_PARALLELISM = 8


class KdfParams(BaseModel):
    """OWASP-baseline Argon2id parameters with strict validation.

    Distinct from the manifest-side
    :class:`aeat.adapters.persistence.storage.bucket.ManifestKdfParams`
    record: that record carries whatever parameter set the bucket was
    enrolled under (so a future cost-bump is non-breaking); this record
    pins the parameter window the substrate accepts for new enrolments
    and rejects anything outside it.
    """

    model_config = _STRICT_FROZEN

    algorithm: Literal["argon2id"]
    version: Literal[19]
    memory_cost: int = Field(ge=_MIN_MEMORY_COST_KIB, le=_MAX_MEMORY_COST_KIB)
    time_cost: int = Field(ge=_MIN_TIME_COST, le=_MAX_TIME_COST)
    parallelism: int = Field(ge=_MIN_PARALLELISM, le=_MAX_PARALLELISM)
    salt: bytes
    output_length: Literal[32]

    @field_validator("salt")
    @classmethod
    def _check_salt_length(cls, value: bytes) -> bytes:
        return require_kdf_salt_length(value, error_type=StorageValidationError)

    @field_serializer("salt")
    def _serialise_salt(self, value: bytes) -> str:
        return encode_kdf_salt(value)

    @field_validator("salt", mode="before")
    @classmethod
    def _decode_salt(cls, value: object) -> bytes:
        return decode_kdf_salt(value, error_type=StorageValidationError)

    @classmethod
    def default(cls) -> KdfParams:
        """Return a :class:`KdfParams` instance with the canonical OWASP 2024 Argon2id baseline parameters."""
        return cls(
            algorithm="argon2id",
            version=_ARGON2_V13,
            memory_cost=_MIN_MEMORY_COST_KIB,
            time_cost=_MIN_TIME_COST,
            parallelism=_MIN_PARALLELISM,
            salt=secrets.token_bytes(_SALT_BYTES),
            output_length=_OUTPUT_BYTES,
        )

    def to_manifest_params(self) -> ManifestKdfParams:
        """Return this canonical parameter set as a :class:`ManifestKdfParams` bucket-manifest shape."""
        from ..bucket import ManifestKdfParams

        return ManifestKdfParams.model_validate(self.model_dump())


__all__ = ["KdfParams"]
